# WebAuthnとパスキー認証

パスキー認証では、**RP（Webサービス）は公開鍵を保持し、認証器は秘密鍵を保持する**。認証時に秘密鍵そのものを送るのではなく、RPが発行した一回限りのチャレンジを含むデータへ認証器が署名し、RPが公開鍵で検証する。

## 1. パスキー登録時

```mermaid
sequenceDiagram
    autonumber
    actor User as 利用者
    participant RP as RPサーバー（Webサービス）
    participant Client as ブラウザ／OS（WebAuthnクライアント）
    participant Auth as 認証器／パスキープロバイダー

    User->>Client: 利用者がログイン済み画面で「パスキーを追加」を選ぶ
    Client->>RP: ブラウザがセッションCookieを付けてパスキー登録開始要求を送る
    RP->>RP: RPサーバーがセッションを検証し、その利用者へのパスキー追加を許可する
    RP->>RP: RPサーバーが一回限りのchallengeを生成し、登録処理と対応付けて一時保持する
    RP-->>Client: RPサーバーがchallenge、RP情報、user情報、公開鍵アルゴリズムなどを含む登録オプションを返す
    Client->>Client: ブラウザがtype、challenge、originを含むclientDataJSONを作成する
    Client->>Auth: ブラウザ／OSがRP ID、user情報、公開鍵アルゴリズム、SHA-256(clientDataJSON)などを認証器へ渡す
    Auth-->>User: 認証器が、端末ロック解除のPIN・生体情報などによる利用者確認を要求する
    User->>Auth: 利用者が認証器に対して本人確認操作を行う（PIN・生体情報そのものはRPへ送らない）
    Auth->>Auth: 認証器がRP ID用の公開鍵・秘密鍵ペアとcredential IDを生成する
    Auth->>Auth: 認証器が秘密鍵、credential ID、RP ID、user handleを資格情報として保持する
    Auth-->>Client: 認証器がcredential IDと、公開鍵を含むauthenticator data／attestationを返す
    Client->>RP: ブラウザがcredential ID、clientDataJSON、attestationObjectを登録応答として送る
    RP->>RP: RPサーバーがchallenge、origin、RP ID hash、形式・アルゴリズム、必要なattestation条件を検証する
    RP->>RP: RPサーバーが利用者アカウントとcredential ID・公開鍵を対応付けて保存する
    RP-->>Client: RPサーバーが登録成功を返す
```

### 登録後に誰が何を保持するか

| 主体 | 継続して保持するもの | 保持しない／相手へ送らないもの |
|---|---|---|
| 認証器／パスキープロバイダー | 秘密鍵、credential ID、RP ID、user handleなど | 秘密鍵や生体情報をRPサーバーへ送らない |
| RPサーバー | 利用者アカウント、credential ID、公開鍵、必要に応じて署名カウンタなど | 利用者の秘密鍵や生体情報を保持しない |
| ブラウザ／OS | 登録処理中のオプションと応答を仲介する | 原則としてRP用秘密鍵をWebページへ渡さない |
| 利用者 | PINを記憶する場合がある | 指紋・顔などの生体情報は認証器側のローカル照合に使い、RPへ送らない |

## 2. パスキー認証時

```mermaid
sequenceDiagram
    autonumber
    actor User as 利用者
    participant RP as RPサーバー（Webサービス）
    participant Client as ブラウザ／OS（WebAuthnクライアント）
    participant Auth as 認証器／パスキープロバイダー

    User->>Client: 利用者がRPのログイン操作を開始する
    Client->>RP: ブラウザがログイン開始要求と、必要に応じて利用者IDを送る
    RP->>RP: RPサーバーが一回限りのchallengeを生成し、認証処理と対応付けて一時保持する
    RP-->>Client: RPサーバーがchallenge、RP ID、必要に応じてallowCredentialsなどの認証オプションを返す
    Client->>Client: ブラウザがtype、challenge、originを含むclientDataJSONを作成する
    Client->>Auth: ブラウザ／OSがRP ID、候補credential ID、SHA-256(clientDataJSON)などを認証器へ渡す
    Auth->>Auth: 認証器がRP IDに対応するパスキーを選ぶ
    Auth-->>User: 認証器がPIN・生体情報などによる利用者確認を要求する
    User->>Auth: 利用者が認証器に対して本人確認操作を行う（PIN・生体情報そのものはRPへ送らない）
    Auth->>Auth: 認証器がauthenticatorDataとSHA-256(clientDataJSON)の連結値を秘密鍵で署名する
    Auth-->>Client: 認証器がcredential ID、authenticatorData、signature、必要に応じてuserHandleを返す
    Client->>RP: ブラウザがcredential ID、clientDataJSON、authenticatorData、signature、userHandleを認証応答として送る
    RP->>RP: RPサーバーがcredential IDに対応する利用者と登録済み公開鍵を取得する
    RP->>RP: RPサーバーがchallenge、origin、RP ID hash、UP／UVフラグ、署名、必要に応じて署名カウンタを検証する
    alt すべての検証に成功
        RP->>RP: RPサーバーが利用者を認証済みにし、ログインセッションを作成する
        RP-->>Client: RPサーバーがセッションCookieまたはトークンを返す
        Client->>Client: ブラウザ／アプリがCookieまたはトークンを保持する
    else いずれかの検証に失敗
        RP-->>Client: RPサーバーが認証を拒否し、ログインセッションを作成しない
    end
```

### 認証時に実際に送るもの

| 送信者 → 受信者 | 主な送信物 | 受信者が行うこと |
|---|---|---|
| RPサーバー → ブラウザ／OS | `challenge`、RP ID、必要に応じて`allowCredentials` | ブラウザが`clientDataJSON`を作り、認証器へ処理を依頼する |
| ブラウザ／OS → 認証器 | RP ID、候補credential ID、`SHA-256(clientDataJSON)`など | 認証器がRP用資格情報を選び、利用者確認後に署名する |
| 認証器 → ブラウザ／OS | credential ID、`authenticatorData`、`signature`、必要に応じて`userHandle` | ブラウザがWebAuthn認証応答へまとめる |
| ブラウザ／OS → RPサーバー | credential ID、`clientDataJSON`、`authenticatorData`、`signature`、`userHandle` | RPが保存済み公開鍵と要求時の状態を使って検証する |
| RPサーバー → ブラウザ／アプリ | 認証成功後のセッションCookieまたはトークン | 以後のログイン済み通信で提示する |

秘密鍵、PIN、指紋・顔画像は、WebAuthn認証応答としてRPサーバーへ送られない。

## 3. 認証後の通常アクセス

```mermaid
sequenceDiagram
    actor User as 利用者
    participant Client as ブラウザ／アプリ
    participant RP as RPサーバー（Webサービス）

    User->>Client: 利用者がログイン後の画面やAPI操作を要求する
    Client->>RP: ブラウザ／アプリがセッションCookieまたはアクセストークンを付けて要求する
    RP->>RP: RPサーバーがセッションまたはトークンを検証し、利用者と権限を確認する
    RP-->>Client: RPサーバーが認可結果に応じた画面またはAPI応答を返す
```

WebAuthnの署名はログインを成立させるために使う。ログイン成功後の通常リクエストでは、一般に毎回WebAuthn署名を送り直すのではなく、RPが発行したセッションCookieやトークンを使う。

## 4. 認証後の保持状態

```mermaid
flowchart LR
    Auth[認証器／パスキープロバイダー<br/>秘密鍵・credential ID・RP IDを保持]
    Client[ブラウザ／アプリ<br/>セッションCookieまたはトークンを保持]
    RP[RPサーバー<br/>公開鍵・credential IDと利用者の対応を保持<br/>必要に応じてサーバー側セッションを保持]

    Auth -->|認証時だけ署名を生成<br/>秘密鍵は送らない| Client
    Client -->|認証応答を送る<br/>成功後はCookie／トークンを送る| RP
    RP -->|認証後にCookie／トークンを発行| Client
```

同期型パスキーでは、資格情報がOS・パスキープロバイダーの保護された仕組みを通じて利用者の端末間で同期される場合がある。この場合も、RPサーバーが保持するのは公開鍵側であり、RPへ秘密鍵が渡るわけではない。

## 参照資料

- [Web Authentication: An API for accessing Public Key Credentials - Level 3（W3C）](https://www.w3.org/TR/webauthn-3/)
- [Passkeys Developer Documentation](https://passkeys.dev/docs/)
- [FIDO Alliance Specifications Overview](https://fidoalliance.org/specifications-overview/)
