# Active DirectoryとKerberosのチケット認証

```mermaid
sequenceDiagram
    participant C as 利用者端末
    participant DC as ドメインコントローラ（KDC）
    participant S as 利用先サービス

    Note over DC: ADの利用者・端末・グループ情報を管理し、KDCとして認証を提供する
    C->>DC: AS-REQ（利用者IDと事前認証情報）を送る
    DC->>DC: ADの利用者情報を確認する
    DC-->>C: AS-REP（TGTとクライアント・KDC間のセッション鍵）を返す
    Note over C: TGTは「KDCに認証済み」であることを示すチケット
    C->>DC: TGS-REQ（TGTと利用先サービスのSPN）を送る
    DC->>DC: TGTを検証し、サービス利用を認可する
    DC-->>C: TGS-REP（サービスチケット）を返す
    C->>S: AP-REQ（サービスチケットとAuthenticator）を送る
    S->>S: サービスチケットを検証し、利用者を認証する
    S-->>C: サービスへのアクセスを許可する
```

## 要点

- ADは利用者・端末・グループなどを集中管理する基盤であり、ドメインコントローラがKerberosのKDCとして認証を提供する。
- 利用者端末は最初にTGTを得て、その後はサービスごとにサービスチケットを取得する。パスワードを各サービスへ繰り返し送らない。
- `SPN`はサービスを識別する名前であり、KDCはTGTとSPNを基に、そのサービス用チケットを発行する。
