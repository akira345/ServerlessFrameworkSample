# ServerlessFrameworkSample
サーバレスフレームワークのサンプルとして、EC2インスタンスのAMIバックアップを作りました。

## 目的
- 今話題のServerlessFrameworkについて、手を動かしながら動きを見て動作を学ぶ。
    - ついでにCloudFormationについても。
- lambdaの動きを知る。
    - lambda周辺の技術を検証する。
        - CloudWatch
            - CloudWatch Event
            - CloudWatch Logs
        - IAMロール
        - SNSによる通知
- lamdba関数の作成を通してpython3、boto3の使用法を学ぶ。
- 今後ServerlessFrameworkを使用するにあたってのスケルトンプロジェクトを目指す。
---
## ServerlessFrameworkインストール方法
- 使用しているserverless-plugin-aws-alertsプラグインがServerlessFrameworkの最新バージョンに対応していないので、以下のようにしてまとめて入れました。
```
npm install serverless-plugin-aws-alerts serverless -g
```

## 開発環境
- OS:Windows 10 Pro build 1709
- IDE:Pycharm COMMUNITY 2017.03
- Python: 3.6.2
- npm: 3.10.10
- serverless: 1.25.0
    - serverless-plugin-aws-alerts: 1.2.4
- aws cli: aws-cli/1.14.16 Python/2.7.9 Windows/8 botocore/1.8.20

## 初期プロジェクト構築
- 今回はServerlessFrameworkがどういうものなのかを勉強するために、初期プロジェクトを構築し動きを見ながら開発しました。
また、Python3の勉強もかねて、lambdaの開発はpython3としました。
ベースがない状態で作成するのはハードルが高いので、以前作成した[これ](https://gist.github.com/akira345/4aa57e6ec062f03a0b63)
をアレンジしました。
1. 環境設定
    1. aws cli を[ここ](https://docs.aws.amazon.com/ja_jp/cli/latest/userguide/awscli-install-windows.html)よりインストール。
    1. AWSコンソールより、開発用としてAdministratorAccess権限を付与したIAMを作成。
    1. 以下のコマンドを使用し、開発用IAMをセットする。
    今後の開発もあるので、デフォルトリージョンは東京、出力フォーマットはjsonとした。
    ```
    aws configure
    ```
1. 初期プロジェクト構築
    - 今回はCronの代替としてCloudWatch Eventを試したいので、安直にcrontestとしました。
    ```
    sls create -t aws-python3 -p crontest
    ```
1. lambda実行時エラーになっても気づかないと困るので、最初にCloudWatch Logsによるlamdba関数のエラー通知を設定します。
ここでは[serverless-plugin-aws-alerts](https://github.com/ACloudGuru/serverless-plugin-aws-alerts)
を使用します。
(後で分かったのですが、[ここ](https://dev.classmethod.jp/cloud/aws/lambda-ec2instance-change-serverless/)にあるように、プラグインを使用せず直接指定する方法があるようです。)  
この辺りは改良の余地がありそうです。  
今回バージニアリージョン上で作ったのでリージョン指定もしています。
    ```
    provider:
    region: us-east-1 # バージニアリージョン
    functions:
    hello: # ラムダ関数名
        alarms: # CloudWatch Logs アラーム設定
        - name: helloAlerm
            description: hello_alerm_description
            namespace: 'AWS/Lambda'
            metric: Errors # 大文字小文字間違えると取れないし、特にエラーにもならない・・(Duration、Errors、Invocations、Throttles)
            threshold: 1 # 閾値
            statistic: Sum
            period: 60
            evaluationPeriods: 1 # サンプリング数？
            comparisonOperator: GreaterThanOrEqualToThreshold # >=の意味

    custom:
    alerts:
        stages: # この指定は良く分からない・・・
        - production
        - staging

        dashboards: true # CloudWatchダッシュボードに出すか？

        topics:
        ok: # OK用トピック
            topic: ${self:service}-${opt:stage}-alerts-ok
            notifications:
            - protocol: email
                endpoint: me@example.com # SNSトピック通知先メールアドレス
        alarm: # アラート用トピック
            topic: ${self:service}-${opt:stage}-alerts-alarm
            notifications:
            - protocol: email
                endpoint: me@example.com # SNSトピック通知先メールアドレス


    plugins:
    - serverless-plugin-aws-alerts
    ```
1. ラムダ関数を実装します。  
ローカル実行機能があるようですが、良く分からなかったので、開発時は単体スクリプトとして動作するものを作成し、それを持っていきました。
1. デプロイ
    - AWSへデプロイします。何故かステージングでデプロイすると
    ```
    Serverless: Warning: Not deploying alerts on stage stage
    ```
    となってCloudWatchアラートが作成されなかったので、
明示的にproduction指定しています。
    ```
    sls deploy -s productions -v
    ```
    なお、変更して再デプロイしても更新されないことがあったので、その場合は、
    ```
    sls remove -s productions -v
    ```
    と一旦リソースを全部削除して再デプロイすると良いです。
1. CloudWatchアラートテスト
    - デプロイされたら、SNSトピックの認証メールが飛ぶので承認します。
    - デプロイされたラムダ関数をテストします。ここではまだIAM指定をしていないので、実行に失敗するはずです。
    これで、CloudWatchアラートで指定したSNSへアラートメールが飛ぶことを確認します。
1. IAMロール指定
    - ラムダ関数実行用IAMロール権限設定を行います。
    Qiitaとか見ると、CloudWatchLogsへの権限設定を行っている例があるのですが、特に設定しなくてもFrameWork側で設定しているようで問題ないようです。（この辺り要検証）
    ハマり所として、DescribeInstancesはResourceで
    ```
    arn:aws:ec2:*
    ```
    としても権限がないエラーになります・・・
    ```
    providers:
      iamRoleStatements:
    - Effect: "Allow"
      Action:
        - "ec2:DescribeSnapshots"
        - "ec2:DeregisterImage"
        - "ec2:CreateImage"
        - "ec2:DescribeInstances"
        - "ec2:DescribeImages"
        - "ec2:DeleteSnapshot"
      Resource:
        - "*"
1. CloudWatchEventによるスケジュール設定  
ここではテストの為5分間隔で実行させます。
    ```
    functions:
      hello:
        events:
          - schedule: rate(5 minutes)
    ```
1. テスト
    1. EC2インスタンスを作成し、以下のようにタグ設定をします。
        - Name: example.com　（インスタンス名）
        - backup: On　（バックアップするか）
        - generation: 3 (無指定の場合３になります。)
    2. 5分待ってAMIが作成されることを確認します。
    3. しばらく動かして、指定した世代数+1がローテーションされていることを確認します。
---
- 学んだこと
    - ServerlessFrameworkについて
        - ServerlessFrameworkはlambda開発で使用するフレームワークではなく、CloudFormationのラッパツールである。
        - serverless.ymlに設定することで、CloudFormationが作成され、AWSへデプロイされる。
        - CloudFormationでデプロイされるので、リソース一式削除することができる。
    - lambda(python)について
        - 関数内の標準出力、ログ出力はCloudWatch Logsへ出力される。
        - 定時実行したい場合は、CloudWatch Eventを使用し、lambda関数を呼び出す。
        - CloudWatch Logsは指定した文字列、エラー状況などをメトリックとしSNSトピックへ通知することができる。
        - ログの出力は以下のようにする。
            ```
            import logging
            logger = logging.getLogger()
            logger.setLevel(logging.INFO)
            def hoge():
              logger.info("InfoLog")
              foo = "var"
              logger.info("Valiable:{}".format(foo))
            ```
        - Python Tips
            - 文字列を小文字にする。
                ```
                foo = "Abcde"
                print (foo.lower()) # abcde
                ```
            - List型に格納されているDictionaly型の特定キーで降順にソートする。
                ```
                from operator import itemgetter
                image_list = ret["Images"]
                sort_list = sorted(image_list, key=itemgetter("Name"), reverse=True)
                ```
            - if文で and/orは`&&、||`ではなく、`and/or`
            - nullは`None`で、比較する場合は、`is None`もしくは`is not None`であり、`!=None`とかしてはいけない(らしい)。ついでに`and/or`は論理値を返すとは[限らないらしい](https://qiita.com/keisuke-nakata/items/e0598b2c13807f102469)
            - Pythonの`True/False`は実は`1/0`である。なので、`True+1`とか`False+1`ができる。[参考](http://programming-study.com/technology/python-ifnone/)
            - List型でキーがない場合エラーになるので存在チェックをしないといけない。
            ```
            for device in image["BlockDeviceMappings"]:
                if "VirtualName" in device and device["VirtualName"].startswith("ephemeral"):
            ```
        - boto3について
            - Pagenaters
                - リソース取得の際、全部のリソースを返さず、一部だけ返すメソッドがある。
                その際、Makerとかセットして取得する必要があるが、それをラップし、イテレータとして使えるようにしたもの。（という理解）
                SDK for Rubyでいうeach_pageと同様（という理解）
                でも、結果セットにMakerがあったりするので、これで全件取得できるのだろうか確信が持てていない・・[参考](https://boto3.readthedocs.io/en/latest/guide/paginators.html)
                    ```
                    paginator = ec2.get_paginator('describe_instances')
                    page_iterator = paginator.paginate
                    for page in page_iterator:
                        # Some Prosecc
                    ```
            - エラーコードについて
                メソッドの実行エラーは`ClientError`で取得可能ですが、**ErrorCodeにコードが入っているとは限らない。**
                ```
                from botocore.exceptions import ClientError
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
                ```
                ```
                s3 = boto3.resource('s3')
                bucket = s3.Bucket(bucket_name)
                try:
                    bucket.Object(log_file_name).load()
                except ClientError as e:
                    print(e.response)
                    if e.response["Error"]["Code"] == "404":
                        # 存在しないのは何もしない
                        pass
                    else:
                        raise
                ```
            
        - lambda内タイムゾーンについて
            - lambda内部の時刻はUTCです。時刻取得の際はハンドラ関数内で取得しないと[時刻がおかしくなる](https://qiita.com/yutaro1985/items/a24b572624281ebaa0dd)らしい。
                - pythonでutc->jst変換
                    ```
                    from datetime import datetime, timedelta, timezone
                    jst = timezone(timedelta(hours=+9), 'JST')
                    str_jst_time = datetime.strftime(datetime.now(jst), "%Y%m%d%H%M")
                    ```
            - 他にも[環境変数にセット](https://qiita.com/nullian/items/39ecf1f6d0194b72e8e6)する事でタイムゾーンを変更することができるようです。
    - その他
        - SNSのメール送信先などは環境変数へセットするほうがいい。
        - Prod/Devの切り替えができるようにファイルを分離したほうがいい。
        - 複数のラムダ関数をデプロイする際に今のままだと共通のIAMロールやCloudWatchEventになるので分離方法を探す。
        - プロジェクトのディレクトリ構成についてベストプラクティスがないか調べてみる。
        - 複数のラムダ関数をSNSで連携やCloudWatchEventで何かしらのトリガをベースに呼び出すとかやってみる。[ここ](https://dev.classmethod.jp/cloud/aws/ami-and-snapshot-delete/)とか手軽そう。
