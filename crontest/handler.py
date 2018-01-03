import boto3
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
from operator import itemgetter
from datetime import datetime, timedelta, timezone
from botocore.exceptions import ClientError

# 指定したインスタンスIDのタグ配列を取得する
def check_tag_set(ec2, instance_id):
    response = ec2.describe_instances(
        InstanceIds=[
            instance_id,
        ]
    )
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            return instance["Tags"]


# 指定したインスタンスIDのタグをチェックしバックアップの有無と保存世代数を返す
def check_backup_config(ec2, instance_id):
    backup_config = {}
    backup_config["backup_sw"] = False
    backup_config["generation"] = 3
    tag_set = check_tag_set(ec2, instance_id)
    ##################################
    logger.info("TagSet:{}".format(tag_set))
    ##################################
    for tag in tag_set:
        if (tag["Key"].lower() == "backup") and (tag["Value"].lower() == "on"):
            backup_config["backup_sw"] = True

        if tag["Key"].lower() == "generation":
            try:
                backup_config["generation"] = int(tag["Value"])
            except ValueError:
                backup_config["generation"] = None

    return backup_config


# 指定したインスタンスIDのイメージを探索し、保存世代数を超えるイメージIDハッシュを返す
def check_delete_images(ec2, instance_id):
    backup_config = check_backup_config(ec2, instance_id)
    ret = ec2.describe_images(
        Filters=[
            {
                'Name': 'name', # 小文字注意
                'Values': [
                    '*__' + instance_id + "-*",
                ]
            },
            {
                'Name': 'state',
                'Values': [
                    "available" # 地味にAMI作成に失敗するのがあるので成功しているもののみ対象とする
                ]
            }
        ],
        Owners=[
            'self',
        ],
    )
    image_list = ret["Images"]
    sort_list = sorted(image_list, key=itemgetter("Name"))
    ##################################
    logger.info("describe_images:{}".format((sort_list)))
    ##################################
    delete_images = sort_list[backup_config["generation"]:len(sort_list)]
    ##################################
    logger.info("RemoveImageCount:{}".format(len(delete_images)))
    ##################################
    return delete_images


def hello(event, context):
    ec2 = boto3.client('ec2', region_name='us-east-1')
    ##################################
    logger.info("StartAMIBackup")
    ##################################
    # リージョン内にあるすべてのEC2インスタンスを探索
    paginator = ec2.get_paginator('describe_instances')
    page_iterator = paginator.paginate(
        Filters=[
            {
                'Name': 'instance-state-name',
                'Values': [
                    'running',
                ]
            },
        ]
    )
    for page in page_iterator:
        for reservation in page["Reservations"]:
            for instance in reservation["Instances"]:
                ###################################
                logger.info("Starting Backup Instance:{}".format(instance["InstanceId"]))
                ###################################
                instance_id = instance["InstanceId"]
                jst = timezone(timedelta(hours=+9), 'JST')
                image_name = instance_id + "-" + datetime.strftime(datetime.now(jst), "%Y%m%d%H%M")
                comment = "Automatically Backup AMI"
                backup_config = check_backup_config(ec2,instance_id)
                ##################################
                logger.info(backup_config)
                ##################################
                if backup_config["backup_sw"] and backup_config["generation"] is not None:
                    ##################################
                    logger.info("instance {} Start backup".format(instance_id))
                    ##################################
                else:
                    ##################################
                    logger.info("instance {} Backup configuration are not correctly".format(instance_id))
                    ##################################
                    continue
                tag_set = check_tag_set(ec2, instance_id)
                for tag in tag_set:
                    # インスタンスのNameタグにあるサーバ名を取得
                    if tag["Key"].lower() == "name" and tag["Value"] is not None:
                        # 使えない文字を変換
                        image_name = tag["Value"].replace("*","x") + "__" + image_name
                ##################################
                logger.info("{}:Creating".format(image_name))
                ##################################
                # AMI作成(非同期実行なので結果応答を待たない)
                try:
                    ec2.create_image(
                        Description=comment,
                        InstanceId=instance_id,
                        Name=image_name,
                        NoReboot=True
                    )
                except ClientError as e:
                    if e.response["Error"]["Code"] == 'InvalidAMIName.Duplicate':
                        # 1分未満のAMI取得は無視する。
                        ##################################
                        logger.info("Wait for minuts!")
                        continue
                    else:
                        raise

                # 不要なAMIを削除
                ##################################
                logger.info("Remove Old Backup Start")
                ##################################
                delete_images = check_delete_images(ec2, instance_id)
                if len(delete_images) == 0:
                    logger.info("No image to be deleted")
                else:
                    logger.info("Remove old backups")
                    logger.info(delete_images)
                    for image in delete_images:
                        logger.info(image["ImageId"])
                        logger.info(image["State"])
                        if image["State"] == "available":
                            ##################################
                            logger.info("DeRegisterImage:{}".format(image["ImageId"]))
                            ##################################
                            try:
                                ec2.deregister_image(
                                    ImageId = image["ImageId"]
                                )
                            except ClientError as e:
                                if e.response["Error"]["Code"] == 'InvalidAMIID.Unavailable':
                                    # 偽物イメージをつかまされることがあるので、無視する
                                    logger.info("にせもの")
                                    continue
                                else:
                                    raise
                            ##################################
                            logger.info("DeleteSnapshot Start")
                            ##################################
                            for device in image["BlockDeviceMappings"]:
                                if "VirtualName" in device and device["VirtualName"].startswith("ephemeral"):
                                    continue
                                else:
                                    ##################################
                                    logger.info("DeletingSnapshot:{}".format(device["Ebs"]["SnapshotId"]))
                                    ##################################
                                    ec2.delete_snapshot(
                                        SnapshotId = device["Ebs"]["SnapshotId"]
                                    )
