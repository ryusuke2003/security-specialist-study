# CSRFトークンとSameSite

## 前提と登場人物

被害者はECサイトへログイン済みで、**ブラウザが認証Cookieを保持**している。ECサイトはセッションに結び付いた予測不能なCSRFトークンを正規フォームへ埋め込む方式とする。攻撃者サイトは別サイトで、正規フォームのトークンを読めず、ECサイトにXSSはないものとする。

## 攻撃を止める主体はどこか

```mermaid
sequenceDiagram
    autonumber
    participant X as 攻撃者サイト
    participant B as 被害者ブラウザ
    participant A as ECサイト

    B->>A: ブラウザが認証Cookie付きで住所変更フォームを要求する
    A-->>B: ECサイトがセッションに対応するCSRFトークン入りフォームを返す
    B->>X: ブラウザが攻撃者ページを取得する
    X-->>B: 攻撃者サイトがECサイトへの自動送信フォームを返す
    B->>B: ブラウザがクロスサイトPOSTへのCookie送信条件を判断する
    alt ブラウザが認証Cookieを付けない
        B->>A: ブラウザが認証CookieなしのPOSTを送る
        A->>A: ECサイトが未認証として住所変更を拒否する
    else ブラウザが認証Cookieを付ける
        B->>A: ブラウザがCookie付きPOSTを送る<br/>正しいCSRFトークンは含まれない
        A->>A: ECサイトが受信トークンをセッションの期待値と照合する
        alt ECサイトがトークン欠落・不一致を拒否する
            A-->>B: ECサイトが住所変更を実行せずエラーを返す
        else ECサイトがトークンを検証しない脆弱な実装
            A->>A: ECサイトが被害者の住所を不正に変更してしまう
        end
    end
```

## 処理後に残るもの

| 主体 | 保持するもの・結果 |
|---|---|
| 被害者ブラウザ | ECサイトのCookieと正規フォームのトークン。別サイトのスクリプトへ自由に渡さない |
| ECサイト | セッションとトークンの対応。検証失敗なら住所は変更しない |
| 攻撃者サイト | 偽フォーム。通常、ECサイトの正しいトークンは保持しない |

## 注意点

**SameSiteを実施するのはブラウザ、トークンを検証するのはECサイト。** 明示的な`SameSite=Lax`は通常のクロスサイトPOSTへのCookie送信を制限し、`Strict`はさらに厳しく制限する。Laxにはトップレベルの安全なメソッドによる遷移等の例外があり、状態変更をGETで実装してはいけない。属性省略時の挙動と明示的Laxも区別する。

SameSiteは「リクエストそのものを必ず送らなくする」設定ではない。またsiteとoriginは同一概念ではなく、同一site内の別originからの攻撃やXSSへの万能策ではない。[CORS](CORSのpreflightと認証情報付きリクエスト.md)によるレスポンス読取り制限とも役割が異なる。

## 参照資料

- [OWASP：CSRF Prevention Cheat Sheet（Synchronizer Token・SameSite）](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
