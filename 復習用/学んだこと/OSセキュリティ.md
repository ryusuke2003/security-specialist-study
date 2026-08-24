# OSセキュリティ

## 2026-08-17

### Active DirectoryとKerberos

- Active Directory（AD）は、組織内の利用者・端末・グループなどを一元管理するディレクトリサービスであり、ドメインコントローラが認証などを担う。
- Kerberosは、パスワードを各サービスへ都度送らずにチケットで認証する方式である。利用者は最初にTGTを得て、必要なサービス用チケットを取得して利用する。
- 流れ: [Active DirectoryとKerberosのチケット認証](../流れ図/ActiveDirectoryとKerberosのチケット認証.md)
