# IPsecトンネルモードとIKE

## 前提と登場人物

**IKEv2で鍵・相手・通信範囲を確立し、ESPで実データを保護する**拠点間VPNの例である。端末AとBの間を、VPNゲートウェイAとBが中継する。以下は通常のIKE_AUTHによる相互認証とESPの暗号化・完全性保護を使い、EAP、NAT越え、再鍵交換は省略する。

SAは暗号方式・鍵・SPI等をまとめた通信の取り決めである。IKE SAはIKEの制御通信を保護し、CHILD SAがESP用の方向別SAを用意する。

## 1. VPNゲートウェイ同士がIKEで準備する

```mermaid
sequenceDiagram
    autonumber
    participant A as VPNゲートウェイA
    participant B as VPNゲートウェイB

    A->>B: GW-AがIKE_SA_INITを送る<br/>暗号候補・DH公開値・nonce
    B-->>A: GW-BがIKE_SA_INIT応答を返す<br/>採用方式・DH公開値・nonce
    A->>A: GW-Aが自分のDH秘密値と相手の公開値等からIKE用の鍵を導出する
    B->>B: GW-Bが同様にIKE用の鍵を導出する
    A->>B: GW-Aが暗号化・完全性保護したIKE_AUTHを送る<br/>ID・認証データ・ESP用提案とSPI・通信範囲
    B->>B: GW-Bが相手の認証データと提案した通信範囲を検証する
    B-->>A: GW-Bが保護したIKE_AUTH応答を返す<br/>ID・認証データ・採用SAとSPI・通信範囲
    A->>A: GW-Aが相手の認証データと採用条件を検証する
    Note over A,B: 相互認証成功時だけ、両GWが方向別のESP用SA・鍵を利用する
```

証明書認証なら相手証明書と署名、事前共有鍵認証ならその鍵に基づく認証データを検証する。秘密鍵・事前共有鍵・DH共有秘密をそのまま送るわけではない。認証や条件の確認に失敗したら、ESP通信へ進まない。

## 2. VPNゲートウェイがESPで元のIPパケットを運ぶ

```mermaid
sequenceDiagram
    autonumber
    participant A as 端末A 10.1.0.10
    participant GA as VPNゲートウェイA
    participant GB as VPNゲートウェイB
    participant B as 端末B 10.2.0.20

    A->>GA: 端末Aが10.2.0.20宛ての元IPパケットを送る
    GA->>GA: GW-Aが保護ポリシーと送信SAを選び、元IPパケット全体をESPで保護する
    GA->>GB: GW-Aが外側IPパケットを送る<br/>GW-AからGW-B宛て・SPIと連番・暗号化された内側・認証データ
    GB->>GB: GW-BがSPI等で受信SAを選び、再送・完全性・復号結果を確認する
    alt GW-Bの検証に成功した
        GB->>B: GW-Bが復元した元IPパケットを端末Bへ転送する
    else GW-Bの検証に失敗した
        GB->>GB: GW-Bが破棄し、端末Bへ転送しない
    end
```

インターネットのルータは外側IPヘッダのGW宛先で配送する。ESPトンネルでは元のIPヘッダも内側で保護されるが、外側IPヘッダ自体がESPで暗号化されるわけではない。

## 処理後に残るもの

| 主体 | 保持するもの・見える範囲 |
|---|---|
| 両VPNゲートウェイ | 認証設定、IKE SA、方向別ESP SA、鍵、SPI、送受信連番等 |
| 端末A・B | 本来の端末間通信。拠点間VPNだけなら通常はGWのIPsec鍵を持たない |
| 中継ルータ | 外側IPヘッダ等。暗号化された内側IPパケットは読めない |

## 注意点

SPIは鍵そのものではなく、受信側がSAを選ぶための識別子である。ESP SAは方向別なので、A→BとB→Aを一つの共通状態として描かない。拠点内区間までこのVPNだけで暗号化されるとは限らず、必要ならTLS等も使う。

## 参照資料

- [RFC 7296 §1.2・§2.15：IKEv2と認証](https://www.rfc-editor.org/rfc/rfc7296.html)
- [RFC 4303 §2・§3：ESPトンネルと受信処理](https://www.rfc-editor.org/rfc/rfc4303.html)
