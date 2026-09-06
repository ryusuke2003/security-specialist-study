# SAMLによるSSO

## 前提と登場人物

**利用者を認証するのはIdP、Assertionを検証して自分用セッションを作るのはSP**である。ここでは会社のIdPと勤怠SaaSのSPが、署名検証鍵・識別子・返送先等を設定済みとする。

以下はSP起点のWeb SSOで、認証要求はリダイレクト、SAML ResponseはHTTPSのフォームPOSTでブラウザが運ぶ構成例である。IdP起点SSOや別のbindingは省略する。

## 1. SPがブラウザをIdPへ案内する

```mermaid
sequenceDiagram
    autonumber
    actor U as 利用者
    participant B as ブラウザ
    participant S as 勤怠SaaSのSP
    participant I as 会社のIdP

    U->>B: 利用者が勤怠SaaSを開く
    B->>S: ブラウザが勤怠画面を要求する
    S->>S: SPが未ログインと判断し、AuthnRequestのIDを一時保持する
    S-->>B: SPがAuthnRequest付きのIdP向けリダイレクトを返す
    B->>I: ブラウザがAuthnRequestとIdP用Cookie等を送る
    alt IdPが有効な既存セッションを確認した
        I->>I: IdPが再認証要件を確認し、既存ログインを利用する
    else IdPでログインや再認証が必要
        I-->>B: IdPがログイン・MFA画面を返す
        U->>B: 利用者がIdPの画面で認証操作を行う
        B->>I: ブラウザがIdPへ認証情報・操作結果を送る
        I->>I: IdPが利用者を認証する
    end
    Note over I: IdPで認証に失敗した場合は成功Assertionを発行しない
```

## 2. SPがAssertionを検証してログイン状態を作る

```mermaid
sequenceDiagram
    autonumber
    participant I as 会社のIdP
    participant B as ブラウザ
    participant S as 勤怠SaaSのSP

    I->>I: IdPが利用者・対象SP・有効期間等を含むAssertionへ署名する
    I-->>B: IdPが署名済みAssertionを含むSAML ResponseのPOSTフォームを返す
    B->>S: ブラウザがSPのACSへSAML ResponseをPOSTする
    S->>S: SPが信頼済みIdP鍵で署名を検証し、署名された内容だけを利用する
    S->>S: SPが発行者・宛先・Audience・期限・要求IDとの対応・再利用を検証する
    alt SPの検証に成功した
        S->>S: SPが利用者を対応付け、権限を確認してSP用セッションを作る
        S-->>B: SPが自分用のセッションCookieを返す
        B->>S: ブラウザがSP用Cookieで以後の勤怠画面を要求する
    else SPの検証に失敗した
        S-->>B: SPがログインを拒否し、セッションを発行しない
    end
```

ACSはSPがSAML Responseを受け取る窓口である。Response全体への署名等を使う構成もあるが、いずれも署名検証済みの要素と実際に利用する利用者情報を一致させる必要がある。

## 処理後に残るもの

| 主体 | 保持するもの | 相手へ渡さないもの |
|---|---|---|
| IdP | 署名秘密鍵、利用者情報、IdP用ログイン状態 | IdPの署名秘密鍵、利用者のパスワードをSPへ渡さない |
| SP | 信頼済みIdPの検証鍵・設定、SP用セッション、再送検出等の状態 | IdPの秘密鍵は不要 |
| ブラウザ | IdP用CookieとSP用Cookieを別々に保持。一時的にSAML Responseを仲介 | IdPのCookieをSP用Cookieとして流用しない |

## 注意点

SSOは、一度のログインを別の連携サービスでも利用できることを指す。別SPを開いた際も、そのSP向けのAssertion検証とセッション発行は行う。ブラウザを通ったAssertionを無条件に信用したり、IdPの認証成功だけでSPの全機能を許可したりしない。

## 参照資料

- [OWASP：SAML Security Cheat Sheet（Redirect/POST、署名・要求対応・再送検証）](https://cheatsheetseries.owasp.org/cheatsheets/SAML_Security_Cheat_Sheet.html)
