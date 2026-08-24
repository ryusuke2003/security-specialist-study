# DKIMの署名と検証

DKIM（DomainKeys Identified Mail）は、送信側がメールの本文と選択したヘッダへ電子署名を付け、受信側がDNSで公開鍵を取得して検証する仕組みです。これにより、署名対象が配送中に改ざんされていないことと、`d=`で示すドメインの管理者が署名したことを確認します。

```mermaid
sequenceDiagram
    participant Admin as example.jpのメール管理者
    participant Client as 送信者のメールソフト・業務アプリ
    participant Sender as example.jpの送信メールサーバ
    participant DNS as example.jpの権威DNS
    participant Receiver as 受信メールサーバ
    participant Policy as DMARC評価

    Admin->>DNS: 管理者がselector1._domainkey.example.jpにDKIM公開鍵をTXTで公開する

    Client->>Sender: メール本文と送信ヘッダ（From、To、Subjectなど）を送る
    Sender->>Sender: 送信サーバが必要に応じてDate、Message-IDなどのヘッダを付加する
    Sender->>Sender: 受信した本文と選んだ既存ヘッダを正規化してハッシュ化する
    Sender->>Sender: 送信サーバがDKIM秘密鍵でハッシュへ署名する
    Sender->>Sender: 送信サーバがd=example.jp、s=selector1、h=署名対象ヘッダ、bh=本文ハッシュ、b=署名値をDKIM-Signatureへ入れる
    Sender->>Receiver: 送信サーバがDKIM-Signature付きメールを送信する

    Receiver->>Receiver: 受信サーバがDKIM-Signatureからd=とs=を取り出す
    Receiver->>DNS: 受信サーバがselector1._domainkey.example.jpのTXTを問い合わせる
    DNS-->>Receiver: DNSがDKIM公開鍵を返す
    Receiver->>Receiver: 受信サーバが同じ本文と対象ヘッダを正規化してハッシュ化する
    Receiver->>Receiver: 受信サーバがDNS公開鍵でb=の署名を検証する

    alt 本文・対象ヘッダが改ざんされておらず署名が有効
        Receiver->>Receiver: 受信サーバがDKIM=passを記録する
        Receiver->>Policy: 受信サーバがDKIM認証済みドメインとFromドメインのalignmentを渡す
    else 本文・対象ヘッダが改ざんされた、又は公開鍵・署名が不正
        Receiver->>Receiver: 受信サーバがDKIM=failを記録する
        Receiver->>Policy: 受信サーバがSPF結果と合わせてDMARCポリシーを評価する
    end
```

## 覚えるポイント

- `d=`は署名ドメイン、`s=`は公開鍵を選ぶselectorである。受信側は`<selector>._domainkey.<d=>`をDNSで引く。
- 秘密鍵は送信メールサーバだけが保持し、DNSへ公開するのは公開鍵である。
- 本文とFrom・To・Subjectなどの送信ヘッダは、送信者のメールソフトや業務アプリがメールサーバへ渡す。送信サーバもDateやMessage-IDなどを付加でき、その中から署名対象の既存ヘッダを選んで署名する。
- DKIMが守るのは署名対象に含めた本文・ヘッダだけである。署名対象外のヘッダ追加や、メーリングリストによる本文変更などは、構成によって検証結果へ影響する。
- `DKIM=pass`だけでは表示上の差出人が正当とは言い切れない。DMARCでは、DKIMの`d=`ドメインと表示上の`From`ドメインがalignmentしているかも確認する。
- DKIMの失敗は直ちに受信拒否を意味しない。SPF結果とDMARCの`p=`ポリシーを合わせて、受信・隔離・拒否を判断する。
