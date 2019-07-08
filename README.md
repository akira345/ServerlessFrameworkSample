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
- lamdba関数のRubyサポートをテストする。
- 今後ServerlessFrameworkを使用するにあたってのスケルトンプロジェクトを目指す。
---
## ServerlessFrameworkインストール方法
- 使用しているserverless-plugin-aws-alertsプラグインが何故かこのバージョンのServerlessで読み込めなかったので、グローバルではなくローカルに入れます。
```
npm install serverless -g
npm install serverless-plugin-aws-alerts
```

## 開発環境
- OS:Windows 10 Pro build 17763
- IDE:VSCode
- Python: 3.7.3
- npm: 6.9.0
- serverless: 1.46.1
    - serverless-plugin-aws-alerts: 1.2.4
- aws cli: aws-cli/1.16.193 Python/3.7.3 Windows/10 botocore/1.12.183

## 初期プロジェクト構築
- 今回はServerlessFrameworkがどういうものなのかを勉強するために、初期プロジェクトを構築し動きを見ながら開発しました。
また、LambdaがRuby対応したので、以前作成した[これ](https://gist.github.com/akira345/4aa57e6ec062f03a0b63)
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
    sls create -t ruby -p crontest
    ```
1. lambda実行時エラーになっても気づかないと困るので、最初にCloudWatch Logsによるlamdba関数のエラー通知を設定します。
ここでは[serverless-plugin-aws-alerts](https://github.com/ACloudGuru/serverless-plugin-aws-alerts)
を使用します。
(後で分かったのですが、[ここ](https://dev.classmethod.jp/cloud/aws/lambda-ec2instance-change-serverless/)にあるように、プラグインを使用せず直接指定する方法があるようです。)  
この辺りは改良の余地がありそうです。  
今回東京リージョン上で作ったのでリージョン指定もしています。
    ```
    provider:
    region: ap-northeast-1 # 東京リージョン
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
    - Gemの自動パッキングはしてくれないようなので、手動でやります。
    ```
    bundle install --path vendor/bundle
    ```
    - AWSへデプロイします。
    ```
    sls deploy -s staging -v
    ```
    なお、変更して再デプロイしても更新されない場合は、
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
        - Rubyへの対応も問題なさそう。ただしGem回りとタイムゾーンは要注意。
    - lambda(Ruby)について
        - 関数内の標準出力、ログ出力はCloudWatch Logsへ出力される。これはPythonと同じ。
        - 定時実行したい場合は、CloudWatch Eventを使用し、lambda関数を呼び出す。
        - CloudWatch Logsは指定した文字列、エラー状況などをメトリックとしSNSトピックへ通知することができる。
        - lambda内タイムゾーンについて
            - lambda内部の時刻はUTCです。時刻取得の際はハンドラ関数内で取得しないと[時刻がおかしくなる](https://qiita.com/yutaro1985/items/a24b572624281ebaa0dd)らしい。
                - Rubyでutc->jst変換(要ActiveSupport)
                    ```
                    Time.now.in_time_zone('Japan')
                    ```
            - 他にも[環境変数にセット](https://qiita.com/nullian/items/39ecf1f6d0194b72e8e6)する事でタイムゾーンを変更することができるようです。
