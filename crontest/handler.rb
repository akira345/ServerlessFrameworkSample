# -*- coding: utf-8 -*- 
require 'net/http'
require 'aws-sdk-core'
require 'aws-sdk-ec2'
require 'active_support'
require 'active_support/core_ext'
require 'pp'

## インスタンスの対象からタグを取得する
def check_tag_set(ec2,instance_id)
  tag_set = ec2.describe_instances({
    instance_ids: [
      instance_id
    ]
  })
  return tag_set.reservations[0].instances[0].tags 
end

## 取得したタグからバックアップの設定を確認します
def check_backup_config(ec2,instance_id)
  backup_config = Hash.new
  backup_config[:backup_sw] = false
  backup_config[:generation] = 3
  tag_set = check_tag_set(ec2,instance_id)
  tag_set.each do |tag|
    if tag[:key].downcase == 'backup' && tag[:value] == 'on'
      backup_config[:backup_sw] = true
    end
    if tag[:key].downcase == 'generation'
      backup_config[:generation] = tag[:value]
    end
  end
  return backup_config
end

## バックアップの世代から多すぎるものを特定する
def check_delete_images(ec2,instance_id)
  backup_config = check_backup_config(ec2,instance_id)
  image_list = ec2.describe_images({
    owners: ["self"],
    filters: [
      {
        name: "name",
        values: ['*__' + instance_id + '-*']
      },
      {
        name: "state",
        values: [
          "available" # 地味にAMI作成に失敗するのがあるので成功しているもののみ対象とする
        ]
      }
    ]
  }).images
  sort_list = image_list.sort { |a,b| b[:name] <=> a[:name] }
  return sort_list[backup_config[:generation].to_i, sort_list.length]
end

def hello(event:, context:)
  ec2 = Aws::EC2::Client.new(
    region: 'ap-northeast-1'
  )
  ## リージョン内にあるすべてのEC2インスタンスを探索
  ec2.describe_instances({
    filters: [
      {
        name: "instance-state-name",
        values: [
          "running"
        ]
      }
    ]
  }).each_page do |resp|
    resp.reservations.each do |reservation|
      reservation.instances.each do |instance|
        instance_id = instance.instance_id 
        image_name = instance_id + '-' + Time.now.in_time_zone('Japan').strftime("%Y%m%d%H%M") #ラムダ内はUTC
        comment = "Automatically Backup AMI"
        backup_config = check_backup_config(ec2,instance_id)
        if backup_config[:backup_sw] && backup_config[:generation] != nil
          puts "Start backup in #{instance_id}"
        else
          puts "Backup configuration are not correctly in #{instance_id}"
          break
        end

        tag_set = check_tag_set(ec2, instance_id)
        tag_set.each do |tag|
          if tag.key.downcase == "name" && tag.value != nil
            # 使えない文字を変換
            image_name = tag.value.gsub("*","x") + "__" + image_name
          end
        end

        begin
          ## バックアップ対象であればバックアップ、異なれば終了
          ec2.create_image({
            instance_id: instance_id, 
            description: comment,
            name: image_name,
            no_reboot: true
          })
        rescue Aws::EC2::Errors::InvalidAMINameDuplicate
          # 1分未満のAMI取得は無視する。
          ##################################
          pp "Wait for minuts!"
        end

        ## バックアップされているもので不要となった世代のものを削除する
        delete_images = check_delete_images(ec2,instance_id)
        unless delete_images.nil?
          puts "Remove old backup"
          delete_images.each do |image|
            begin
              ec2.deregister_image({
                image_id: image[:image_id]
              })
            rescue Aws::EC2::Errors::InvalidAMIIDUnavailable
              # 偽物イメージをつかまされることがあるので、無視する
              pp "にせもの"
            end
            image[:block_device_mappings].each do |device|
              break if device[:virtual_name].to_s.start_with?("ephemeral") #ephemeral領域は取らない
              ec2.delete_snapshot(:snapshot_id => device[:ebs][:snapshot_id])
            end
          end
        end
      end
    end
  end
end
