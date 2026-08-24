# OAuth 2.0 / OIDCの認可コードとPKCE

```mermaid
sequenceDiagram
    participant User as 利用者ブラウザ
    participant Client as Webアプリ
    participant IdP as 認可・認証サーバ

    Client->>Client: アプリがランダムなcode_verifierを生成して保持する
    Client->>Client: code_verifierをSHA-256で変換し、code_challengeを作る
    Client->>User: アプリがcode_challenge付き認可要求へ誘導する
    User->>IdP: 利用者が認証し、同意する
    IdP-->>User: IdPが認可コードをリダイレクトURIへ返す
    User->>Client: ブラウザが認可コードをアプリへ渡す
    Client->>IdP: アプリが認可コードとcode_verifierをトークンエンドポイントへ送る
    IdP->>IdP: IdPがcode_verifierからchallengeを計算して照合する
    IdP-->>Client: IdPがアクセストークンとIDトークンを返す
    Client->>Client: アプリがIDトークンを検証して利用者を認証する
```

- OAuth 2.0は、クライアントへAPIアクセス権限を委譲する認可の仕組みである。
- OIDCはOAuth 2.0の上でIDトークンを使い、利用者が誰かをクライアントが確認する認証を提供する。
- PKCEは、公開クライアントから認可コードが横取りされても、最初に作った`code_verifier`を持たない攻撃者がトークンへ交換できないようにする。
- `code_verifier`はクライアントが最初に生成して保持する秘密のランダム値である。認可要求にはその変換値である`code_challenge`だけを送り、トークン交換時に元の`code_verifier`を送って照合する。
