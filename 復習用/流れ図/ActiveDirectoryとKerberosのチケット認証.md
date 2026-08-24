# Active DirectoryとKerberosのチケット認証

```mermaid
sequenceDiagram
    participant C as 利用者端末
    participant DC as ドメインコントローラ（AD DS / Kerberos KDC）
    participant S as 利用先サービス

    Note over DC: 【AD】利用者・端末・グループ情報を管理する。DCは、その情報を参照するKerberosのKDC役も兼ねる。
    Note over C,S: 【Kerberos】以下のAS・TGS・APのチケット認証手順を行う。
    Note over C,DC: 1. AS（Authentication Service）: 最初のログオンでTGTを得る
    C->>DC: AS-REQ（利用者IDと事前認証情報）を送る
    DC->>DC: ADの利用者情報を確認する
    DC-->>C: AS-REP（TGTとクライアント・KDC間のセッション鍵）を返す
    Note over C: TGTは「KDCに認証済み」であることを示すチケット
    Note over C,DC: 2. TGS（Ticket Granting Service）: 利用先ごとのサービスチケットを得る
    C->>DC: TGS-REQ（TGTと利用先サービスのSPN）を送る
    DC->>DC: TGTを検証し、サービス利用を認可する
    DC-->>C: TGS-REP（サービスチケット）を返す
    Note over C,S: 3. AP（Application Service）: サービスへチケットを提示する
    C->>S: AP-REQ（サービスチケットとAuthenticator）を送る
    S->>S: サービスチケットを検証し、利用者を認証する
    S-->>C: サービスへのアクセスを許可する
```

## 要点

- ADは利用者・端末・グループなどを集中管理する基盤であり、ドメインコントローラがKerberosのKDCとして認証を提供する。
- 図の`【Kerberos】`と示した範囲にある`AS-REQ / AS-REP / TGS-REQ / TGS-REP / AP-REQ`、TGT、サービスチケットの流れが**Kerberos**である。ADそのものは認証方式ではなく、KerberosのKDCが参照する利用者・端末・グループ情報などを管理する基盤である。
- 利用者端末は最初にTGTを得て、その後はサービスごとにサービスチケットを取得する。パスワードを各サービスへ繰り返し送らない。
- `SPN`はサービスを識別する名前であり、KDCはTGTとSPNを基に、そのサービス用チケットを発行する。
