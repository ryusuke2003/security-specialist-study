# SAMLによるSSO

SAMLは、**会社のログイン窓口（IdP）で一度本人確認すると、連携先サービス（SP）へ個別のパスワード入力なしで入れるようにする仕組み**です。

たとえば、社員が社内ポータルから勤怠SaaSや経費精算SaaSを使う場面で利用されます。各SaaSがパスワードを個別に管理する代わりに、IdPが「この人は認証済み」と保証します。

```mermaid
sequenceDiagram
    participant User as 利用者
    participant Browser as ブラウザ
    participant SP as 勤怠SaaS（SP）
    participant IdP as 会社の認証基盤（IdP）

    User->>Browser: 利用者が勤怠SaaSを開く
    Browser->>SP: ブラウザが勤怠SaaSへアクセスする
    SP-->>Browser: SPがIdPへの認証要求を付けてリダイレクトする
    Browser->>IdP: ブラウザが会社の認証基盤へ移動する

    alt IdPで未認証
        IdP-->>Browser: IdPがログイン画面を表示する
        User->>IdP: 利用者がID・パスワードや多要素認証で本人確認を行う
    else IdPで認証済み
        IdP->>IdP: IdPが既存のログイン状態を確認する
    end

    IdP->>IdP: IdPが「利用者は認証済み」と示すSAML Assertionを作成し署名する
    IdP-->>Browser: IdPがAssertionを含むフォームをSPへ送るようブラウザへ返す
    Browser->>SP: ブラウザがSAML Assertionを勤怠SaaSへ送る
    SP->>SP: SPがAssertionの署名・発行者・宛先・有効期限を検証する

    alt Assertionの検証に失敗
        SP-->>Browser: SPがログインを拒否する
    else Assertionの検証に成功
        SP-->>Browser: SPが自分用のセッションを発行する
        Browser-->>User: 利用者が勤怠SaaSを利用できる
    end
```

## 4つだけ覚える

- **IdP（Identity Provider）**: 会社の認証基盤。利用者本人を認証し、認証済みだと保証する。
- **SP（Service Provider）**: 勤怠・経費精算などの利用先サービス。IdPの保証を検証して利用を許可する。
- **SAML Assertion**: 「この利用者は認証済み」「誰であるか」などを表す、IdP署名付きの情報。
- **SSO（Single Sign-On）**: 一度のログインで複数サービスを使える状態。

## 間違えやすい点

- SAMLで認証するのは**IdP**、Assertionを受け取り検証するのは**SP**です。
- Assertionはブラウザを経由してSPへ届きますが、SPはそのまま信用せず、署名・発行者・宛先・有効期限を検証します。
- SAMLは主に組織向けのWeb SSOでよく使われます。OAuth 2.0は主に「APIへ何を許可するか」の認可、OIDCはOAuth 2.0上の認証連携であり、同じものではありません。
