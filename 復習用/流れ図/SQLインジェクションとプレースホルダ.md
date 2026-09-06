# SQLインジェクションとプレースホルダ

## 前提と登場人物

**SQLを組み立てるのはWebアプリ、SQLを実行するのはDB**である。攻撃者の文字列入力をuser_idの検索条件へ入れる例で、脆弱な文字列連結と、パラメータ化クエリを比較する。

## 1. 脆弱な例：Webアプリが入力をSQL本文へ連結する

```mermaid
sequenceDiagram
    autonumber
    actor X as 攻撃者
    participant A as Webアプリ
    participant D as DB

    X->>A: 攻撃者が検索値として ' OR '1'='1 を送る
    A->>A: Webアプリが入力をSQL文字列へ直接連結する
    A->>D: Webアプリが変更されたSQL本文を送る<br/>WHERE user_id = '' OR '1'='1'
    D->>D: DBがORを値の文字列ではなくSQL構文として解釈する
    D-->>A: DBが本来の検索条件を超えた行を返してしまう
```

攻撃者がDBへ直接接続するのではなく、WebアプリがDBへ送るSQLの構造を入力経由で変えさせている。

## 2. 対策：WebアプリがSQLの構造と値を分離する

```mermaid
sequenceDiagram
    autonumber
    actor X as 入力者
    participant A as WebアプリとDBドライバ
    participant D as DB

    X->>A: 入力者が同じ文字列 ' OR '1'='1 を送る
    A->>A: Webアプリが固定したSQLひな形とパラメータを別々にDBドライバへ渡す
    A->>D: DBドライバがパラメータ化したクエリを実行する<br/>WHERE user_id = ? と別パラメータ値
    D->>D: DBが入力全体を一つの値として比較し、OR条件へ変えない
    D-->>A: DBが本来のSQL条件に従う結果だけを返す
```

図の送信は論理的な処理である。prepareとexecuteの通信回数やプレースホルダ記号はDB・ドライバによる。単に`?`を文字列置換する自作処理ではなく、正しいパラメータ化APIを使う。

## 処理後に残るもの

| 主体 | 保持するもの・結果 |
|---|---|
| Webアプリ | SQLひな形、別パラメータとして渡す入力値、検索結果 |
| DB | SQLの構造に従った実行結果。入力を勝手にSQL構文へ昇格させない |
| 入力者 | アプリが返した応答。アプリ側の認可も別途必要 |

## 注意点

パラメータ化で束縛するのは値である。テーブル名・列名・並び順等を利用者が選べる場合は、固定候補へのマッピング等を使う。入力検証やWAFは補助策で、文字列連結による根本問題の修正を代替しない。

## 参照資料

- [OWASP：SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
