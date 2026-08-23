# DNSキャッシュポイズニングとDNSSEC

```mermaid
sequenceDiagram
    participant U as 利用者
    participant R as 検証するキャッシュDNSサーバ
    participant P as 親ゾーン（.jp）
    participant A as 子ゾーン（example.jp）

    U->>R: www.example.jp の A レコードを問い合わせ
    R->>P: example.jp の DS レコードを問い合わせ
    P-->>R: DS（子ゾーンDNSKEYのハッシュ）とRRSIG
    Note right of R: ルートの信頼アンカーから<br/>親ゾーンまでの署名は検証済み
    R->>A: Aレコード、RRSIG、DNSKEYを問い合わせ
    A-->>R: Aレコード、RRSIG、DNSKEY
    R->>R: DNSKEYのハッシュがDSと一致するか確認
    R->>R: DNSKEYでAレコードのRRSIGを検証

    alt 信頼の連鎖と署名が有効
        R-->>U: 検証済みのAレコードを返す
        Note right of R: 検証済みとしてキャッシュする
    else DS・DNSKEY・RRSIGのいずれかの検証に失敗
        R-->>U: 応答を利用しない（通常はSERVFAIL）
        Note right of R: 偽造・改ざんの可能性を検出し、キャッシュしない
    end
```

## DNSSECで確認するもの

- `RRSIG`はDNSレコード群（RRset）に付く電子署名、`DNSKEY`はその署名を検証する公開鍵である。
- `DS`は親ゾーンに置く「子ゾーンのDNSKEYのハッシュ」である。親から子へたどれるようにすることで、ルートを起点とした信頼の連鎖を作る。
- DNSSECは、問い合わせや応答を暗号化する仕組みではない。DNS応答が正しいゾーンにより作られ、途中で改ざんされていないことを検証する仕組みである。
