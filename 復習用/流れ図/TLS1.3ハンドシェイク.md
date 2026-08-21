# TLS 1.3ハンドシェイク

この図は、Forward Secrecyを得るECDHE鍵共有を使う典型的なTLS 1.3の流れです。まず「何をするか」を8段階で追い、その下で各メッセージの中身を確認します。TLS 1.2以前とはメッセージの順序や暗号化される範囲が異なります。

```mermaid
sequenceDiagram
    participant Browser as ブラウザ
    participant Server as Webサーバ
    participant Store as ブラウザの信頼ストア

    Browser->>Server: 1. ブラウザがClientHelloを送る
    Server->>Browser: 2. WebサーバがServerHelloを返す
    Note over Browser,Server: 3. 双方がECDHEの一時鍵から同じ共有秘密を計算し、ハンドシェイク用鍵を導出する
    Note over Browser,Server: 以後のハンドシェイクメッセージはハンドシェイク用鍵で暗号化される

    Server->>Browser: 4. WebサーバがCertificateを送る
    Server->>Browser: 5. WebサーバがCertificateVerifyを送る
    Browser->>Store: 6. ブラウザが信頼ストアからルートCA証明書を取得する
    Browser->>Browser: 6. ブラウザが証明書チェーンとCertificateVerifyを検証する
    Server->>Browser: 7. WebサーバがFinishedを送る
    Browser->>Browser: 7. ブラウザがWebサーバのFinishedを検証する

    alt 検証に失敗
        Browser-->>Server: ブラウザが接続を中止する
    else 検証に成功
        Browser->>Server: 7. ブラウザが自分のFinishedを送る
        Note over Browser,Server: 双方がFinishedを検証したらハンドシェイク完了
        Browser->>Server: 8. ブラウザがアプリケーションデータを送る
        Server->>Browser: 8. Webサーバがアプリケーションデータを返す
    end

    Note over Browser,Server: 一時秘密鍵は通信後に破棄する。後から長期秘密鍵が漏えいしても、記録済み通信の復号を困難にする（Forward Secrecy）
```

1. **ClientHello**
   - ブラウザが対応するTLSバージョン・暗号方式・SNIと、ECDHE用の一時公開鍵を送る。
   - SNIは「`example.com` に接続したい」とWebサーバへ知らせる情報である。

2. **ServerHello**
   - Webサーバが採用するTLSバージョン・暗号方式と、ECDHE用の一時公開鍵を返す。

3. **共有秘密とハンドシェイク用鍵の導出**
   - 双方が自分の一時秘密鍵と相手の一時公開鍵から、同じ共有秘密をそれぞれ計算する。共有秘密そのものは送らない。
   - この共有秘密からハンドシェイク用の暗号鍵を導出する。以降の`Certificate`などは暗号化される。

4. **Certificate**
   - Webサーバがサーバ証明書と、必要な中間CA証明書をブラウザへ送る。
   - 証明書にはサーバ公開鍵、SAN、発行者CA、CAの署名などが入っている。

5. **CertificateVerify**
   - Webサーバが、証明書内の公開鍵に対応する秘密鍵でハンドシェイク内容へ署名する。
   - ブラウザは「このWebサーバは、送ってきた証明書に対応する秘密鍵を本当に持つ」と確認できる。

6. **証明書チェーンと署名の検証**
   - ブラウザは信頼ストア内のルートCAを起点に、CA署名・有効期限・SANの接続先名・必要に応じて失効状態を検証する。
   - `example.com` へ接続した場合、SANに `example.com` があり、チェーンも正しいことを確認して「この相手は本当に `example.com` 用の証明書を持つWebサーバ」と判断する。

7. **Finishedの相互検証**
   - Webサーバとブラウザは、それまでのハンドシェイク内容から計算した検証値を`Finished`として送り合う。
   - これにより、途中のハンドシェイク全体が改ざんされていないことを確認する。

8. **アプリケーションデータ通信**
   - 共有秘密から別途導出したアプリケーションデータ用鍵で、HTTPなどの上位プロトコルのデータを暗号化・認証して通信する。

## ECDHEの共有秘密から、実際の通信を守るまで

TLS 1.3では、ECDHEの共有秘密をそのまま暗号鍵として使いません。HKDFで用途ごとの秘密値を導出してから、送信方向ごとにAEADの鍵とIVを作ります。

```mermaid
flowchart TD
    CPUB["ブラウザの一時公開鍵"]
    CSEC["ブラウザの一時秘密鍵"]
    SPUB["Webサーバの一時公開鍵"]
    SSEC["Webサーバの一時秘密鍵"]
    CSHARED["ブラウザが CSEC と SPUB から計算する共有秘密"]
    SSHARED["Webサーバが SSEC と CPUB から計算する共有秘密"]
    SAME{"同じ共有秘密？"}
    TRANSCRIPT["これまでのハンドシェイクメッセージのハッシュ"]
    HKDF["HKDF-Extract / HKDF-Expand-Labelで用途別の秘密値を導出"]
    HS["ハンドシェイク用の送受信traffic secret"]
    APP["アプリケーションデータ用の送受信traffic secret"]
    KEYIV["各traffic secretから AEAD鍵とIVを導出"]
    FIN["finished keyを導出し、ハンドシェイク全体のハッシュへHMACを計算"]
    RECORD["平文HTTPデータ・追加認証データ・AEAD鍵・nonceを入力"]
    AEAD["AES-GCMまたはChaCha20-Poly1305で暗号化と認証"]
    OUT["暗号文と認証タグを送信"]
    VERIFY{"受信側が認証タグを検証できる？"}
    ACCEPT["復号してHTTPデータを受理"]
    REJECT["改ざん・鍵不一致として破棄"]

    CSEC -->|"ブラウザが相手の一時公開鍵と組み合わせる"| CSHARED
    SPUB --> CSHARED
    SSEC -->|"Webサーバが相手の一時公開鍵と組み合わせる"| SSHARED
    CPUB --> SSHARED
    CSHARED --> SAME
    SSHARED --> SAME
    SAME -->|"双方で同じ値になる"| HKDF
    TRANSCRIPT -->|"traffic secretの導出とFinished検証に使う"| HKDF
    HKDF --> HS
    HKDF --> APP
    HS --> FIN
    TRANSCRIPT --> FIN
    APP --> KEYIV
    KEYIV --> RECORD
    RECORD --> AEAD
    AEAD --> OUT
    OUT --> VERIFY
    VERIFY -->|"タグが正しい"| ACCEPT
    VERIFY -->|"タグが不正"| REJECT
```

### ① ECDHE：共有秘密を双方で計算する

- ブラウザとWebサーバは、一時的な公開鍵を交換します。
- 各自が「自分の一時秘密鍵」と「相手の一時公開鍵」から、同じ共有秘密を計算します。
- 共有秘密そのものや一時秘密鍵は送信しません。これが、一時秘密鍵を破棄した後の過去通信を守りやすいForward Secrecyにつながります。

### ② HKDF：用途・方向ごとの鍵材料を分ける

- 共有秘密と、それまでのハンドシェイクメッセージのハッシュを材料に、HKDFでハンドシェイク用とアプリケーションデータ用の`traffic secret`を分けて導出します。
- さらに、ブラウザ送信方向とWebサーバ送信方向の秘密値も別です。一方の送信鍵を、そのまま逆方向には使いません。
- 各`traffic secret`から、実際にレコードを保護する**AEAD鍵**と**IV**を導出します。送信ごとの連番をIVと組み合わせてnonceを作ります。

### ③ 改ざん検知：通常の通信ではAEADの認証タグを使う

- TLS 1.3の通常のレコード通信では、暗号用鍵と独立したMAC用鍵を作って「メッセージ + MAC用鍵」を別計算する構成ではありません。
- AES-GCMやChaCha20-Poly1305の**AEAD**が、暗号化と認証タグの生成を一体で行います。受信側は同じ方向の鍵・IV・連番からnonceを再現し、タグを検証できなければ復号結果を使いません。
- ただしハンドシェイク完了時の`Finished`は別です。`finished key`を導出し、ここまでのハンドシェイク全体のハッシュへHMACを計算して、交渉内容の改ざんを検知します。

> 覚え方: **ECDHEで共有秘密を作る → HKDFで用途別・方向別の鍵材料を作る → AEADで暗号文と認証タグを一緒に作る。**

補足: `EncryptedExtensions` はServerHelloの後、Certificateの前に送られるサーバ設定のメッセージである。この図では、8段階の主な流れに集中するため省略している。
