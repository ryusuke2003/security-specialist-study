# OAuth 2.0 / OIDCの認可コードとPKCE

## 前提と登場人物

この図は**サーバーサイドWebアプリ**をクライアントとする、OIDCの認可コードフロー＋PKCEの例である。ブラウザ、Webアプリのサーバ、認可・認証サーバ、APIサーバを区別する。HTTPSを使い、redirect URI等は登録済みとする。

利用者は認可・認証サーバの画面でログインする。Webアプリのサーバは認可コードを受け取り、サーバ間通信でトークンへ交換する。SPAやモバイルアプリではクライアントとverifierの保持場所が変わるため、この図のサーバをそのまま当てはめない。

## 1. Webアプリが認可要求を作り、ブラウザがコードを届ける

```mermaid
sequenceDiagram
    autonumber
    participant B as 利用者ブラウザ
    participant C as Webアプリのサーバ
    participant O as 認可・認証サーバ

    B->>C: ブラウザがログイン開始を要求する
    C->>C: Webアプリがcode_verifier・state・<br/>nonceを生成し、開始セッションに対応付ける
    C->>C: WebアプリがverifierからS256方式のcode_challengeを作る
    C-->>B: Webアプリが認可エンドポイントへのリダイレクトを返す<br/>scope=openid・challenge・state・nonce等
    B->>O: ブラウザが認可要求を送り、<br/>利用者のログイン・同意操作を仲介する
    O->>O: 認可・認証サーバが利用者を認証し、認可条件を確認する
    O-->>B: 認可・認証サーバが登録済みcallbackへリダイレクトする<br/>認可コード・state
    B->>C: ブラウザがcallbackへ認可コード・stateを届ける
    C->>C: Webアプリがstateを開始時の値と照合する
    Note over B,C: state不一致や認可エラーならWebアプリは交換へ進まない
```

## 2. Webアプリがコードをトークンへ交換し、APIを使う

```mermaid
sequenceDiagram
    autonumber
    participant B as 利用者ブラウザ
    participant C as Webアプリのサーバ
    participant O as 認可・認証サーバ
    participant A as APIサーバ

    C->>O: Webアプリがトークンエンドポイントへ送る<br/>コード・verifier・redirect URI・クライアント認証等
    O->>O: 認可・認証サーバがコードの有効性・<br/>宛先・クライアント等を検証する
    O->>O: 認可・認証サーバがverifierのS256値を<br/>保存済みchallengeと照合する
    alt 認可・認証サーバの検証に失敗した
        O-->>C: 認可・認証サーバがトークン発行を拒否する
    else 認可・認証サーバの検証に成功した
        O-->>C: 認可・認証サーバがアクセストークンとIDトークンを返す
        C->>C: WebアプリがIDトークンの署名・<br/>iss・aud・exp・nonce等を検証する
        Note over C: IDトークン検証に失敗した場合はログインを成立させない
        C-->>B: Webアプリが検証成功後に自分用のセッションCookieを発行する
        C->>A: Webアプリがアクセストークンを付けてAPIを要求する
        A->>A: APIサーバがトークンの有効性・<br/>対象API・scope等の権限を検証する
        A-->>C: APIサーバが認可に応じた結果または拒否を返す
    end
```

## 処理後に残るもの

| 主体 | 保持するもの | 渡さないもの・寿命 |
|---|---|---|
| Webアプリのサーバ | アクセストークン、検証済み利用者情報、Webアプリ用セッション | verifier・state・nonceは認証試行に結び付けた一時情報。verifierは認可要求へ載せない |
| ブラウザ | Webアプリ用Cookie、認可サーバ用Cookie等をそれぞれの条件で保持 | この構成ではAPI用トークンをブラウザへ渡す必要はない |
| 認可・認証サーバ | 利用者・クライアント登録、コードとchallengeの対応、発行状態 | 一度使ったコードを再利用させない |
| APIサーバ | トークン検証に必要な設定・鍵または照会手段 | Webアプリのverifierは不要 |

## 注意点

PKCEは`BASE64URL(SHA256(code_verifier))`をchallengeとして登録し、コード交換時に照合する。コードを横取りしてもverifierを持たない相手の交換を防ぐ。`state`は開始したブラウザセッションとの対応、OIDCの`nonce`はIDトークンと認証要求との対応に使う。

OAuth 2.0はAPI利用の認可、OIDCはIDトークンによる認証連携である。**IDトークンをAPI用アクセストークンの代わりに送らない。** OAuthだけならIDトークンは発行されない。リフレッシュトークンやトークン更新はこの図では省略した。

## 参照資料

- [RFC 7636 §4：PKCE](https://www.rfc-editor.org/rfc/rfc7636.html)
- [OpenID Connect Core §3.1：認可コードフローとIDトークン検証](https://openid.net/specs/openid-connect-core-1_0.html)
