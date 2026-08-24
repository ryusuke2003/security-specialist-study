# IPsecトンネルモードとIKE

拠点間VPNでは、まずVPNゲートウェイ同士が**IKE**で相互認証し、暗号方式・鍵・通信範囲を定めたSA（Security Association）を確立する。その後、確立済みのSAを使って**ESP**が元のIPパケット全体を保護し、外側IPヘッダで相手のVPNゲートウェイまで届ける。

```mermaid
sequenceDiagram
    participant A as 拠点Aの端末（10.1.0.10）
    participant GWA as 拠点AのVPNゲートウェイ（198.51.100.10）
    participant GWB as 拠点BのVPNゲートウェイ（203.0.113.20）
    participant B as 拠点Bの端末（10.2.0.20）

    Note over GWA,GWB: 1. IKEでIKE SAとIPsec（CHILD）SAを確立する
    GWA->>GWB: IKE_SA_INIT: 暗号方式候補、DH公開値、nonceを送る
    GWB-->>GWA: IKE_SA_INIT応答: 採用方式、DH公開値、nonceを返す
    Note over GWA,GWB: DH共有秘密とnonceから、IKEメッセージを保護する鍵を双方で導出する
    GWA->>GWB: IKE_AUTH（暗号化）: ID・認証情報、ESP用SA候補、通信範囲（10.1.0.0/24 → 10.2.0.0/24）を送る
    GWB-->>GWA: IKE_AUTH応答（暗号化）: ID・認証情報、採用したESP用SA・SPI・通信範囲を返す
    Note over GWA,GWB: 相互認証後、方向ごとのIPsec SAとESP暗号・完全性保護用鍵を確立する

    Note over A,B: 2. 確立済みSAを使い、ESPトンネルモードで実データを保護する
    A->>GWA: 元のIPパケット: 10.1.0.10 → 10.2.0.20（社内データ）
    GWA->>GWA: 送信方向SA（SPI）を選び、元のIPパケット全体をESPで暗号化・完全性保護する
    GWA->>GWB: 外側IPヘッダ（198.51.100.10 → 203.0.113.20）、ESPヘッダ（SPI・連番）、暗号化された内側IPパケット、認証データを送る
    Note over GWA,GWB: インターネット上では外側IPヘッダだけでVPNゲートウェイ間を配送する
    GWB->>GWB: SPIで受信方向SAを特定し、連番を確認してESPの完全性を検証・復号する
    GWB->>B: 復元した元のIPパケット: 10.1.0.10 → 10.2.0.20（社内データ）
```

## 覚えるポイント

- **SA**は、暗号方式・鍵・SPI・通信方向・保護対象の通信範囲（Traffic Selector）などをまとめた「この通信をどう保護するか」の合意である。通常、送信方向と受信方向で別々のSAを持つ。
- **IKE**は、DH鍵共有・相互認証・暗号方式の交渉を行い、IKE自身を保護するIKE SAと、ESP通信に使うIPsec SA（IKEv2ではCHILD SA）を確立する。実データを包むのはIKEではなくESPである。
- **ESPトンネルモード**では、元のIPヘッダを含むIPパケット全体が内側の保護対象になる。外側IPヘッダの宛先は本来の通信先端末ではなく、相手側VPNゲートウェイである。
- 受信ゲートウェイはESPヘッダのSPIでSAを選び、改ざん・再送を確認してから復号する。検証に失敗したパケットは内側ネットワークへ転送しない。
