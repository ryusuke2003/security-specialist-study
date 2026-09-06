# CRLとOCSPの失効確認

## 前提と登場人物

**失効確認を行うTLSクライアント**がWebサーバの証明書を受け取った場面である。CRL配布サーバ、OCSPレスポンダ、Webサーバを区別する。以下は3つの方式の比較であり、全クライアントが毎接続で全部を実施するという意味ではない。キャッシュや製品の方針により実際の通信は異なる。

## 1. CRL：クライアントが一覧を取得して照合する

```mermaid
sequenceDiagram
    autonumber
    participant C as TLSクライアント
    participant D as CRL配布サーバ

    C->>D: TLSクライアントが証明書に対応するCRLを要求する
    D-->>C: CRL配布サーバがCA等の正当な発行者が署名した失効一覧を返す
    C->>C: TLSクライアントがCRLの署名・適用範囲・鮮度を検証する
    C->>C: TLSクライアントが証明書のシリアル番号を一覧と照合する
    Note over C: クライアントは正当な一覧に対象証明書が載っていれば失効と判断する
```

## 2. OCSP：クライアントが対象証明書の状態を照会する

```mermaid
sequenceDiagram
    autonumber
    participant C as TLSクライアント
    participant O as OCSPレスポンダ

    C->>O: TLSクライアントがCertIDを送る<br/>発行者を識別する情報・シリアル番号
    O-->>C: OCSPレスポンダが署名付き応答を返す<br/>対象CertID・状態・thisUpdate等
    C->>C: TLSクライアントが署名・署名者の権限・対象一致・鮮度を検証する
    C->>C: TLSクライアントがgood・revoked・unknownを確認する
```

## 3. OCSP stapling：Webサーバが先に応答を取得して添える

```mermaid
sequenceDiagram
    autonumber
    participant O as OCSPレスポンダ
    participant S as Webサーバ
    participant C as TLSクライアント

    S->>O: Webサーバが自分の証明書のCertIDを照会する
    O-->>S: OCSPレスポンダが署名付きOCSP応答を返す
    S->>S: Webサーバが応答を一時保存し、鮮度に従って更新する
    C->>S: TLSクライアントがTLS接続でstaplingを要求する
    S-->>C: Webサーバが証明書と取得済みOCSP応答を送る
    C->>C: TLSクライアントがOCSP応答の署名・権限・対象一致・鮮度を検証する
    Note over S,C: 応答に署名するのはOCSPレスポンダ。Webサーバは添付する役割
```

## 処理後に残るもの

| 主体 | 保持するもの |
|---|---|
| TLSクライアント | 対象証明書、信頼情報、方針に応じたCRL・OCSPのキャッシュ |
| Webサーバ | 自分の証明書・秘密鍵、stapling用の期限付きOCSP応答 |
| CRL発行者／OCSPレスポンダ | 失効情報、署名用の秘密鍵。秘密鍵自体は応答に含めない |

## 注意点

`revoked`と、`unknown`・タイムアウト・古い応答は同じではない。確認不能時に中止するか、別の情報源を試すか等はクライアントの方針や要件による。**「確認できなければ全ブラウザが必ず切断する」とは限らない。**

`good`は「証明書の全検査に合格」を意味しない。有効期間、接続先名、チェーン等は[別途検証](証明書チェーン検証.md)する。OCSP応答はある時点の状態であり、キャッシュ後の失効が瞬時に反映されるとは限らない。

## 参照資料

- [RFC 5280 §5・§6.3：CRLの検証](https://www.rfc-editor.org/rfc/rfc5280.html)
- [RFC 6960 §2.2・§3.2：OCSP状態と応答の受入条件](https://www.rfc-editor.org/rfc/rfc6960.html)
- [RFC 6066 §8：Certificate Status Request](https://www.rfc-editor.org/rfc/rfc6066.html)
