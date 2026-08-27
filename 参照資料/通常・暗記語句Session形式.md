# 通常・暗記語句Session形式

理解・応用問題（`Mode: diagnosis` または `adaptive`）と暗記語句問題（`Mode: term-recall`）だけに適用する詳細形式である。保存先と共通メタデータは[セッション共通形式](セッション形式.md)を正本とする。

## 理解・応用問題

```markdown
# YYYY-MM-DD セキスペ学習

## Session N

- Created: YYYY-MM-DD
- Status: awaiting_answers
- Mode: adaptive
- Question Count: 6
- Subject B Target: 70–85%

### Q1

- Domain: <分野>
- Primary Terms:
  - `<主要語句>`
- Related Terms:
  - `<関連語句>`
- Level: <1-5>
- Track: <A|B>

### 問題

<問題文>

### 回答

<!-- この行の下に回答を書いてください -->
```

通常Sessionは既定6問とし、理解・応用を問う。初回診断では `Mode: diagnosis`、それ以外では `Mode: adaptive` を使う。内部識別子とCLIでは `--mode standard` を使うが、SessionのModeは `diagnosis` または `adaptive` のままにする。各Qには `### 問題` と `### 回答` を一つずつ置く。

## 暗記語句問題

```markdown
# YYYY-MM-DD セキスペ学習

## Session N

- Created: YYYY-MM-DD
- Status: awaiting_answers
- Mode: term-recall
- Question Count: 10
- Track A/B Target: 40% / 60%

### Q1

- Domain: <分野>
- Primary Terms:
  - `<語句>`
- Related Terms:
  - `<近接語句>`
- Level: 1
- Track: <A|B>

### 問題

<語句>とは何ですか？

### 回答

<!-- この行の下に回答を書いてください -->
```

暗記語句Sessionは依頼された範囲で1〜30問とし、指定がなければ10問にする。各QはPrimary Termを正確に一つだけ持ち、同じSession内で重複させない。全問Level 1の短い語句説明形式にし、Trackによって長文化しない。正答は語句の核を一文で言えることを目安とし、目的・特徴・仕組みの詳説は要求しない。`Mode: term-recall` とCLIの `--mode term-recall` を使う。

Aは `floor(問題数 × 0.40)`、Bは残り全部とする。10問ならA4/B6、5問ならA2/B3にする。カタログのTrack `B` はSessionでも `B`、Track `A` または `A/B` はこのモードの配分上 `A` として出題する。`進捗/語句別理解度.md` のTrackはカタログの値を維持する。

採点後のブロック、記録、状態判定は[採点ワークフロー](../skills/security-specialist-trainer/references/採点ワークフロー.md)を読む。
