# OAuth 2.0 / OIDCの認可コードとPKCE

```mermaid
sequenceDiagram
    participant User as 利用者ブラウザ
    participant Client as クライアント（Webアプリ、SPA、モバイルアプリ）
    participant IdP as 認可・認証サーバ

    Client->>Client: アプリがランダムなcode_verifierを生成して保持する
    Note over Client: サーバーサイドWebアプリではサーバー側で保持する。SPA・モバイルアプリでは利用者端末側で保持する。
    Client->>Client: code_verifierをSHA-256で変換し、code_challengeを作る
    Client->>User: ブラウザをcode_challenge・state付き認可要求へ302で誘導する（フロントチャネル）
    User->>IdP: 利用者が認証し、同意する
    IdP-->>User: 302でリダイレクトURIへ戻す（認可コードとstate）
    User->>Client: ブラウザがcallbackへ認可コードとstateを渡す
    Note over User,Client: stateを照合し、開始したブラウザセッションの認可結果であることを確認する
    Client->>IdP: アプリが認可コードとcode_verifierをトークンエンドポイントへ送る（リダイレクトとは分離された通信）
    IdP->>IdP: IdPがcode_verifierからchallengeを計算して照合する
    IdP-->>Client: IdPがアクセストークンとIDトークンを返す
    Client->>Client: アプリがIDトークンを検証して利用者を認証する
```

- OAuth 2.0は、クライアントへAPIアクセス権限を委譲する認可の仕組みである。
- OIDCはOAuth 2.0の上でIDトークンを使い、利用者が誰かをクライアントが確認する認証を提供する。
- PKCEは、公開クライアントから認可コードが横取りされても、最初に作った`code_verifier`を持たない攻撃者がトークンへ交換できないようにする。
- `code_verifier`はクライアントが最初に生成して保持する秘密のランダム値である。認可要求にはその変換値である`code_challenge`だけを送り、トークン交換時に元の`code_verifier`を送って照合する。
- `code_verifier`の保持場所はクライアントの構成に従う。サーバーサイドWebアプリではWebアプリのサーバー側が保持し、SPAやモバイルアプリでは利用者端末上のアプリが保持する。どちらも、認可コードを受け取ってトークン交換を行うクライアントだけが値を保持することが重要である。
- Authorization Endpointは、利用者のログイン・MFA・同意を画面上で扱うため、ブラウザを介すフロントチャネルとして設計されている。認証・同意後、IdPはブラウザへ302を返し、ブラウザがリダイレクトURIへ認可コードを届ける。アクセストークンはこのリダイレクトへ載せず、認可コードの交換で取得する。
