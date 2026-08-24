# OSセキュリティ

## 2026-08-17

### Active DirectoryとKerberos

- Active Directory（AD）は、組織内の利用者・端末・グループなどを一元管理するディレクトリサービスであり、ドメインコントローラが認証などを担う。
- Kerberosは、パスワードを各サービスへ都度送らずにチケットで認証する方式である。利用者は最初にTGTを得て、必要なサービス用チケットを取得して利用する。
- ADとKerberosは同じものではない。ADは利用者・端末・グループなどを管理する基盤であり、ドメインコントローラがKerberosのKDC（AS/TGS）役を兼ねる。`AS-REQ / AS-REP / TGS-REQ / TGS-REP / AP-REQ`、TGT、サービスチケットを使う一連の手順がKerberosである。
- 流れ: [Active DirectoryとKerberosのチケット認証](../流れ図/ActiveDirectoryとKerberosのチケット認証.md)
