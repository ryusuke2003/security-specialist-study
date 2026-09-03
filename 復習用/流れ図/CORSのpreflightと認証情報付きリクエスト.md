# CORSのpreflightと認証情報付きリクエスト

```mermaid
sequenceDiagram
    participant B as 利用者ブラウザ
    participant A as app.example.jp
    participant API as api.example.jp

    B->>A: Webアプリを表示する
    A->>B: JavaScriptが認証情報付きPATCHを要求する
    Note over B: 別オリジンかつ単純リクエストではない
    B->>API: OPTIONS（Origin・PATCH・要求ヘッダ）
    API-->>B: 許可するOrigin・メソッド・ヘッダ・credentialsを応答
    alt Origin等が許可される
        B->>API: Cookie等を付けたPATCHリクエスト
        API-->>B: Access-Control-Allow-Originに特定Origin、<br/>Access-Control-Allow-Credentials: trueを付けて応答
        B->>B: JavaScriptがレスポンスを読める
    else Origin等が許可されない
        B->>B: 本リクエストを送らない、又は<br/>JavaScriptからレスポンスを読ませない
    end
```

## 要点

- CORSは、別オリジンのページ上のJavaScriptがレスポンスを読めるかをブラウザが制御する仕組みである。HTTPリクエストをネットワーク上で完全に止める仕組みではない。
- `PATCH`、非単純ヘッダ、JSONなどの条件では、ブラウザが本リクエストの前にOPTIONSのpreflightで許可を確認し得る。
- Cookieなどの認証情報を伴うCORSでは、サーバは許可するOriginを具体的に返し、`Access-Control-Allow-Credentials: true`を返す。`Access-Control-Allow-Origin: *`と認証情報の許可は併用できない。
