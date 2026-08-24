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
    Note over Admin,DNS: 同一ドメインでもメールサービス・鍵の世代ごとに公開鍵を分けられる。s=selector1 がどの公開鍵かを一意に選ぶ。

    Client->>Sender: メール本文と送信ヘッダ（From、To、Subjectなど）を送る
    Sender->>Sender: 送信サーバが必要に応じてDate、Message-IDなどのヘッダを付加する
    Sender->>Sender: 受信した本文と選んだ既存ヘッダを正規化してハッシュ化する
    Sender->>Sender: 送信サーバがDKIM秘密鍵でハッシュへ署名する
    Sender->>Sender: 送信サーバがd=example.jp、s=selector1、h=署名対象ヘッダ、bh=本文ハッシュ、b=署名値をDKIM-Signatureへ入れる
    Sender->>Receiver: SMTPでメール全体を配送する（本文、From/To/Subject等のヘッダ、DKIM-Signature〔d=署名ドメイン・s=selector・h=対象ヘッダ・bh=本文ハッシュ・b=署名値〕）

    Receiver->>Receiver: 受信サーバが配送されたメールから本文・ヘッダ・DKIM-Signatureを読み取る
    Receiver->>Receiver: d=example.jp（署名ドメイン）とs=selector1（公開鍵を選ぶ名前）を取り出す
    Receiver->>DNS: s._domainkey.d の形、selector1._domainkey.example.jp のTXTを問い合わせる
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

- `d=`は署名ドメイン（「どのドメインの管理者が署名したか」を示す）、`s=`はそのドメイン内で使う公開鍵を一意に選ぶselector（鍵の世代・用途を分ける名前）である。同じドメインが複数のメールサービスを使う場合や鍵をローテーションする場合も、`s=`で対応する公開鍵を区別できる。受信側は`<selector>._domainkey.<d=>`、すなわち`<s>._domainkey.<d>`をDNSで引く。
- `DKIM-Signature`には、図で示した`d=`・`s=`・`h=`・`bh=`・`b=`のほか、通常は`v=1`（DKIMのバージョン）、`a=`（署名アルゴリズム。例: `rsa-sha256`）、`c=`（canonicalization方式。空白・改行の差異をどこまで許容するか。例: `relaxed/relaxed`）も入る。
- 必要に応じて、`t=`（署名時刻）、`x=`（署名の有効期限）、`i=`（署名者の識別子）、`l=`（本文のうち署名対象にするバイト数）も含められる。
- 秘密鍵は送信メールサーバだけが保持し、DNSへ公開するのは公開鍵である。
- 本文とFrom・To・Subjectなどの送信ヘッダは、送信者のメールソフトや業務アプリがメールサーバへ渡す。送信サーバもDateやMessage-IDなどを付加でき、その中から署名対象の既存ヘッダを選んで署名する。
- DKIMが守るのは署名対象に含めた本文・ヘッダだけである。署名対象外のヘッダ追加や、メーリングリストによる本文変更などは、構成によって検証結果へ影響する。
- `DKIM=pass`だけでは表示上の差出人が正当とは言い切れない。DMARCでは、DKIMの`d=`ドメインと表示上の`From`ドメインがalignmentしているかも確認する。
- DKIMの失敗は直ちに受信拒否を意味しない。SPF結果とDMARCの`p=`ポリシーを合わせて、受信・隔離・拒否を判断する。
