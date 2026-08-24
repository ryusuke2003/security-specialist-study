# DNSSEC

```mermaid
sequenceDiagram
    participant U as 利用者
    participant R as 検証するキャッシュDNSサーバ
    participant Z as ルートゾーン（.）
    participant P as 親ゾーン（.jp）
    participant A as 子ゾーン（example.jp）

    U->>R: www.example.jp の A レコードを問い合わせ
    Note right of R: ルートの信頼アンカー（ルートDNSKEY）は事前に保持する
    R->>Z: .jp の DS RRset と RRSIG(DS) を問い合わせ
    Z-->>R: .jp の DS RRset と RRSIG(DS)
    R->>R: 信頼済みのルートDNSKEYで RRSIG(DS) を検証
    R->>P: .jp の DNSKEY RRset と RRSIG(DNSKEY) を問い合わせ
    P-->>R: .jp の DNSKEY RRset と RRSIG(DNSKEY)
    R->>R: DSに対応する .jp のDNSKEYをハッシュし、ルートのDSと一致するか確認
    R->>R: DSに対応する .jp のDNSKEYを信頼できる鍵として確認
    R->>R: そのDNSKEYで .jp のDNSKEY RRsetの RRSIG(DNSKEY) を検証
    R->>P: example.jp の DS RRset と RRSIG(DS) を問い合わせ
    P-->>R: DS RRset と RRSIG(DS)
    R->>R: .jp のDNSKEYで RRSIG(DS) を検証
    R->>A: DNSKEY RRset と RRSIG(DNSKEY) を問い合わせ
    A-->>R: DNSKEY RRset と RRSIG(DNSKEY)
    R->>R: DSに対応する example.jp のDNSKEYをハッシュし、DSと一致するか確認
    R->>R: DSに対応する example.jp のDNSKEYを信頼できる鍵として確認
    R->>R: そのDNSKEYで example.jp のDNSKEY RRsetの RRSIG(DNSKEY) を検証
    R->>A: A RRset と RRSIG(A) を問い合わせ
    A-->>R: A RRset と RRSIG(A)
    R->>R: 検証済みDNSKEY RRset内の適切なDNSKEYで RRSIG(A) を検証

    alt 信頼の連鎖と署名が有効
        R-->>U: 真正性・完全性を確認したA RRsetを返す
        Note right of R: 検証済みとしてキャッシュする
    else DS・DNSKEY・RRSIGの検証に失敗
        R-->>U: SERVFAILを返す
        Note right of R: 検証済みとして利用・キャッシュしない
    end
```

## DNSSECで確認するもの

- `RRSIG`はDNSレコード群（RRset）に付く電子署名、`DNSKEY`はその署名を検証する公開鍵である。
- `DS`は親ゾーンに置かれる、子ゾーンの**特定のDNSKEY**から計算したダイジェスト（ハッシュ値）を含むレコードである。親ゾーンのDNSKEYで`RRSIG(DS)`を検証してから、DSに対応する子ゾーンDNSKEYのハッシュとDSを照合する。これにより、そのDNSKEYが親ゾーンから信頼される鍵だと確認できる。
- `DS`と`DNSKEY`の照合によって、親ゾーンから子ゾーンのDNSKEYへ信頼をつなぐ。電子署名を検証する組合せは`DNSKEY`と`RRSIG`であり、DSに対応するDNSKEYを起点としてDNSKEY RRsetを検証し、その検証済みDNSKEY RRsetに含まれる適切なDNSKEYでA RRsetなどの`RRSIG`を検証する。典型的にはKSKがDNSKEY RRsetへ、ZSKがA・AAAA・MX・TXTなどのRRsetへ署名する。
- DNSSECは、問い合わせや応答を暗号化する仕組みではない。DNS応答が正当なゾーンの秘密鍵によって署名され、途中で改ざんされていないことを検証する仕組みである。
