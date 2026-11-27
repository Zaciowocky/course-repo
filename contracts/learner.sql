-- learner.db 建表语句（契约⑭：本地画像与记忆库）
-- version: 0.1.0
-- owner: 陈奕霖（成员 B）　会签：成员 C
-- 对应任务书 4.2 学伴记忆库、4.3 画像字段。判定阈值、证据口径与复习规则见 profile-rules.yaml。
--
-- 约定
-- 1. learner.db 只在学生电脑上，由本地 MCP server 独占读写；学伴和工作台不直接打开这个文件。
-- 2. 每次连接后先执行 PRAGMA foreign_keys = ON（SQLite 默认不检查外键）。
-- 3. 时间一律是带时区的 ISO 8601 文本，如 2026-11-27T20:15:00+08:00。
-- 4. 列表和小对象存 JSON 文本，用 json_valid / json_type 检查形状。
-- 5. CHECK 只管三类：数值范围与布尔、JSON 形状、本契约自己定义的状态值（四档、复习盒子、更正状态等）。
--    引用其他契约的枚举（op、item_kind、result、上报档位……）和类型类取值（讲法类型、判定方式……）不写 CHECK：
--    SQLite 改 CHECK 要重建整张表，事件表只追加更不能重建；这些值由本地 MCP server 按契约校验后写入，
--    当前取值写在列注释里。
-- 6. 标 [仅本地] 的列含学生原文或题目原文，永远不上报；report.schema.json 的 additionalProperties:false 从结构上挡住。
-- 7. 记忆四库（mistakes / qa_memory / strategies / sessions）学生可在“我的记录”里查看、导出、逐条删除。
--    事件表只追加，不能逐条改删；“清空我的全部数据”= 删除整个 learner.db 文件。

CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
) STRICT;
-- 启动时读出与本文件头的 version 比对，不兼容就拒绝写入并提示（contracts/README.md 冻结规则）
INSERT INTO meta (key, value) VALUES ('schema_version', '0.1.0');


-- ======================================================================
-- 学习事件：画像的原始依据（任务书 4.3“SQLite 事件表只追加”）
-- 字段与 events.schema.json v0.2 一一对应；布尔存 0 / 1
-- ======================================================================
CREATE TABLE events (
  event_id      TEXT PRIMARY KEY,             -- UUID；schema 里可选，写入时由本地 MCP server 补齐
  ts            TEXT NOT NULL,                -- 发生时间；schema 里可选，写入时补齐。同一时刻按写入顺序（rowid）排
  course_id     TEXT NOT NULL,
  version       TEXT NOT NULL,                -- 课程版本 tag
  session_id    TEXT,                         -- 课节 ID，如 S01
  kp_id         TEXT NOT NULL,
  page_id       TEXT,
  activity_id   TEXT,
  op            TEXT NOT NULL,                -- page_enter / page_leave / interact / answer / hint / ask / revisit / answer_change
  result        TEXT,                         -- correct / incorrect / partial / none
  hint_level    INTEGER CHECK (hint_level BETWEEN 0 AND 4),
  duration_s    INTEGER CHECK (duration_s BETWEEN 0 AND 3600),
  done          INTEGER CHECK (done IN (0, 1)),
  item_kind     TEXT,                         -- check / homework / diagnostic / followup / review
  is_transfer   INTEGER CHECK (is_transfer IN (0, 1)),
  item_hash     TEXT,                         -- 学伴出题的内容哈希（16 位十六进制）
  misconception TEXT                          -- MIS 编码或 other，只出现在做错的作答上
) STRICT;
CREATE INDEX events_kp_ts      ON events (kp_id, ts);
CREATE INDEX events_session_ts ON events (course_id, session_id, ts);

CREATE TRIGGER events_no_update BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'events 只追加，不能修改'); END;
CREATE TRIGGER events_no_delete BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'events 只追加，不能删除'); END;


-- ======================================================================
-- 画像（任务书 4.3）：数据库表是原始依据，profile.json 是每次计算后的快照
-- ======================================================================

-- 基础画像：课程初问卷，学生可改；只有一行
CREATE TABLE student_profile (
  id                  INTEGER PRIMARY KEY CHECK (id = 1),
  goal                TEXT,       -- 学习目标：pass（通过考核）/ understand（理解原理）/ build（能动手实现）
  depth               TEXT,       -- 期望深度：overview / standard / deep
  prior_self          TEXT NOT NULL DEFAULT '{}'
                      CHECK (json_valid(prior_self) AND json_type(prior_self) = 'object'),
                                  -- 各先修领域自述基础，取值 0—3，如 {"python": 2, "probability": 1}
  explain_pref        TEXT NOT NULL DEFAULT '[]'
                      CHECK (json_valid(explain_pref) AND json_type(explain_pref) = 'array'),
                                  -- 讲解偏好：讲法类型按优先顺序排（取值同 strategies.kind），讲法记忆会修正
  pace                TEXT,       -- 节奏：slow / normal / fast
  minutes_per_sitting INTEGER CHECK (minutes_per_sitting > 0),   -- 每次可用时间（分钟）
  report_tier         TEXT,       -- 上报档位：standard / minimal（同 report.schema.json）；NULL = 还没授权，不上报
  report_consent_at   TEXT,       -- 授权时间
  updated_at          TEXT NOT NULL
) STRICT;

-- 课程画像：每个知识点一行
CREATE TABLE kp_state (
  kp_id               TEXT PRIMARY KEY,
  course_version      TEXT NOT NULL,   -- 计算时依据的课程版本；跨版本再绑定时对照迁移清单
  state               TEXT NOT NULL DEFAULT 'unseen'
                      CHECK (state IN ('unseen', 'gap', 'partial', 'transfer')),
                                       -- 四档状态，与 state-gate.yaml、report.schema.json 一致
  pending             INTEGER NOT NULL DEFAULT 1 CHECK (pending IN (0, 1)),
                                       -- 待确认标记：为 1 时 state 不改档，学伴先追问或出诊断题
  pending_reason      TEXT,            -- few_evidence（有效证据不足）/ correction（学生更正待验证）/ kp_changed（知识点改版待复核）
  p_mastery           REAL CHECK (p_mastery BETWEEN 0 AND 1),   -- 掌握概率（BKT）；NULL = 还没有有效证据
  evidence_count      INTEGER NOT NULL DEFAULT 0 CHECK (evidence_count >= 0),     -- 有效证据次数，口径见 profile-rules.yaml
  attempts            INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  correct_alone       INTEGER NOT NULL DEFAULT 0 CHECK (correct_alone >= 0),      -- 独立做对：没用提示（hint_level = 0）
  correct_with_hint   INTEGER NOT NULL DEFAULT 0 CHECK (correct_with_hint >= 0),  -- 提示后做对
  wrong               INTEGER NOT NULL DEFAULT 0 CHECK (wrong >= 0),              -- 做错，含 partial
  transfer_attempts   INTEGER NOT NULL DEFAULT 0 CHECK (transfer_attempts >= 0),
  transfer_correct    INTEGER NOT NULL DEFAULT 0 CHECK (transfer_correct >= 0),   -- 迁移题独立做对次数
  recent_hint_max     INTEGER CHECK (recent_hint_max BETWEEN 0 AND 4),            -- 近 5 次作答的最高提示级别
  ask_count           INTEGER NOT NULL DEFAULT 0 CHECK (ask_count >= 0),          -- 纠结信号：提问
  revisit_count       INTEGER NOT NULL DEFAULT 0 CHECK (revisit_count >= 0),      -- 纠结信号：回跳
  answer_change_count INTEGER NOT NULL DEFAULT 0 CHECK (answer_change_count >= 0),-- 纠结信号：改答
  long_stay_count     INTEGER NOT NULL DEFAULT 0 CHECK (long_stay_count >= 0),    -- 纠结信号：超时停留（阈值见 profile-rules.yaml）
  prereq_gaps         TEXT NOT NULL DEFAULT '[]'
                      CHECK (json_valid(prereq_gaps) AND json_type(prereq_gaps) = 'array'),
                                       -- 先修缺口：状态为 gap 的先修知识点 ID 列表
  half_life_days      REAL CHECK (half_life_days > 0),          -- 遗忘模型：记忆半衰期（天）
  last_success_at     TEXT,                                     -- 最近一次独立做对
  retention           REAL CHECK (retention BETWEEN 0 AND 1),   -- 写入时刻的保持率
  next_review_at      TEXT,                                     -- 知识点层面的下次复习时间
  updated_at          TEXT NOT NULL,
  updated_by          TEXT NOT NULL,   -- 更新来源：event / bkt / forgetting / correction / migration
  CHECK (correct_alone + correct_with_hint + wrong <= attempts),
  CHECK (transfer_correct <= transfer_attempts)
) STRICT;

-- 课程画像的误区列表（每个知识点 × 误区编码一行）
CREATE TABLE kp_misconceptions (
  kp_id         TEXT NOT NULL REFERENCES kp_state (kp_id),
  code          TEXT NOT NULL,             -- 误区编码（取自 knowledge_points.yaml）或 other
  count         INTEGER NOT NULL DEFAULT 1 CHECK (count >= 1),
  first_seen_at TEXT NOT NULL,
  last_seen_at  TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'resolved')),
                                           -- active = 仍在出现；转 resolved 的条件见 profile-rules.yaml
  PRIMARY KEY (kp_id, code)
) STRICT;

-- 课节画像：学习过程中实时更新，每个课节一行
CREATE TABLE lesson_state (
  course_id           TEXT NOT NULL,
  session_id          TEXT NOT NULL,       -- 课节 ID，如 S01
  pinned_version      TEXT NOT NULL,       -- 固定 tag：学到一半不切换课程版本
  warmup_result       TEXT CHECK (warmup_result IS NULL
                                  OR (json_valid(warmup_result) AND json_type(warmup_result) = 'array')),
                                           -- warm-up 诊断题结果 [{"kp_id", "event_id", "result"}]
  warmup_branch       TEXT,                -- 分流去向：direct / remedial / diagnostic / skipped（同 report.schema.json）
  objective_id        TEXT,                -- 当前教学目标 OBJ-…
  current_page_id     TEXT,
  current_activity_id TEXT,
  stuck               TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(stuck) AND json_type(stuck) = 'array'),
                                           -- 卡点 [{"kp_id", "page_id", "since"}]
  return_stack        TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(return_stack) AND json_type(return_stack) = 'array'),
                                           -- 补习返回栈：插短补习后回到哪里 [{"page_id", "activity_id"}]，栈顶在末尾
  activity_status     TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(activity_status) AND json_type(activity_status) = 'object'),
                                           -- 各活动状态 {"ACT-S01-001": "done"}，值为 todo / doing / done
  overlays_used       TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(overlays_used) AND json_type(overlays_used) = 'array'),
                                           -- 本节用过的补充及效果 [{"overlay_id", "kind", "effect"}]
  started_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL,
  PRIMARY KEY (course_id, session_id)
) STRICT;

-- 证据表：每次状态变化写一行，追查判定原因时顺着 event_ids 查到具体事件
CREATE TABLE evidence (
  id              INTEGER PRIMARY KEY,
  kp_id           TEXT NOT NULL REFERENCES kp_state (kp_id),
  event_ids       TEXT NOT NULL CHECK (json_valid(event_ids) AND json_type(event_ids) = 'array'
                                       AND json_array_length(event_ids) >= 1),
                                   -- 来源事件 ID 列表：上一次状态变化之后计入的有效证据
  kind            TEXT NOT NULL,   -- 证据类型（触发这次变化的事件的 item_kind）：check / homework / diagnostic / followup / review
  result          TEXT NOT NULL,   -- 触发事件的结果：correct / incorrect / partial
  weight          REAL NOT NULL DEFAULT 1 CHECK (weight >= 0),
  state_before    TEXT CHECK (state_before IN ('unseen', 'gap', 'partial', 'transfer')),
  state_after     TEXT NOT NULL CHECK (state_after IN ('unseen', 'gap', 'partial', 'transfer')),
  pending_after   INTEGER NOT NULL CHECK (pending_after IN (0, 1)),
  p_mastery_after REAL CHECK (p_mastery_after BETWEEN 0 AND 1),
  created_at      TEXT NOT NULL
) STRICT;
CREATE INDEX evidence_kp ON evidence (kp_id, created_at);

-- 更正记录：学生在工作台发起“我其实会了 / 我其实没懂”，学伴出验证题核实
CREATE TABLE corrections (
  id                INTEGER PRIMARY KEY,
  kp_id             TEXT NOT NULL REFERENCES kp_state (kp_id),
  direction         TEXT NOT NULL CHECK (direction IN ('higher', 'lower')),   -- higher = 我其实会了；lower = 我其实没懂
  reason            TEXT,          -- [仅本地] 学生写的理由
  probe_activity_id TEXT,          -- 触发的验证题：课程题用活动 ID
  probe_item_hash   TEXT,          --               学伴出题用内容哈希
  probe_event_id    TEXT,          -- 验证题的作答事件
  probe_result      TEXT,          -- correct / incorrect / partial；NULL = 还没做
  status            TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected')),
  created_at        TEXT NOT NULL,
  resolved_at       TEXT
) STRICT;


-- ======================================================================
-- 学伴记忆库（任务书 4.2）：存具体事实；学生可逐条删除
-- ======================================================================

-- 错题本：检测题、诊断题、作业批改判错时写入；按五个复习盒子排期
CREATE TABLE mistakes (
  id                INTEGER PRIMARY KEY,
  kp_id             TEXT NOT NULL,
  activity_id       TEXT,          -- 题目 ID：课程题用活动 ID
  item_hash         TEXT,          --          学伴出题用内容哈希（同 events.item_hash）
  stem_snapshot     TEXT NOT NULL, -- [仅本地] 题干快照
  student_answer    TEXT,          -- [仅本地] 学生答案
  answer_ref        TEXT,          -- 正确答案引用：课程题指向活动或页面，学伴题存答案要点
  judged_by         TEXT NOT NULL, -- 判定方式：auto（程序判定）/ agent（学伴判定）/ self（学生自评）
  misconception     TEXT,          -- 误区编码或 other
  hint_level        INTEGER CHECK (hint_level BETWEEN 0 AND 4),   -- 出错时用到的提示级别
  first_wrong_at    TEXT NOT NULL,
  wrong_count       INTEGER NOT NULL DEFAULT 1 CHECK (wrong_count >= 1),
  box               INTEGER NOT NULL DEFAULT 1 CHECK (box BETWEEN 1 AND 5),   -- 复习盒子 1—5
  box5_streak       INTEGER NOT NULL DEFAULT 0 CHECK (box5_streak >= 0),      -- 第 5 盒连续答对次数
  next_review_at    TEXT,
  status            TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'mastered')),
  resolved_strategy TEXT,          -- 最终讲通的讲法（取值同 strategies.kind）
  source_event_id   TEXT,          -- 首次出错的作答事件
  updated_at        TEXT NOT NULL,
  CHECK (activity_id IS NOT NULL OR item_hash IS NOT NULL)
) STRICT;
-- 同一道题只占一行，再错只加 wrong_count（活动 ID 只在课程内唯一，所以带上 kp_id）
CREATE UNIQUE INDEX mistakes_item ON mistakes (kp_id, coalesce(activity_id, ''), coalesce(item_hash, ''));
CREATE INDEX mistakes_due ON mistakes (status, next_review_at);

-- 问答记忆：每次问答结束写入
CREATE TABLE qa_memory (
  id                   INTEGER PRIMARY KEY,
  kp_id                TEXT NOT NULL,
  page_id              TEXT,
  question_raw         TEXT,              -- [仅本地] 学生原问题；学生可只删原文、保留摘要
  question_summary     TEXT NOT NULL,     -- 一句话摘要
  answer_summary       TEXT,
  resolved             INTEGER NOT NULL DEFAULT 0 CHECK (resolved IN (0, 1)),
  followup_activity_id TEXT,              -- 追问验证题：课程题用活动 ID
  followup_item_hash   TEXT,              --             学伴出题用内容哈希
  followup_result      TEXT,              -- correct / incorrect / partial
  struggle             TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(struggle) AND json_type(struggle) = 'array'),
                                          -- 纠结信号 ["revisit", "answer_change", "long_stay"]
  mistake_id           INTEGER REFERENCES mistakes (id) ON DELETE SET NULL,   -- 关联错题
  created_at           TEXT NOT NULL,
  updated_at           TEXT NOT NULL
) STRICT;
CREATE INDEX qa_kp   ON qa_memory (kp_id, created_at);
CREATE INDEX qa_open ON qa_memory (kp_id) WHERE resolved = 0;   -- 未解决的问题，主动回访

-- 讲法记忆：讲解后，下一次独立作答结果回来时更新
CREATE TABLE strategies (
  kp_id            TEXT NOT NULL,
  kind             TEXT NOT NULL,   -- 讲法类型：example / analogy / diagram / code / counterexample
  used_count       INTEGER NOT NULL DEFAULT 0 CHECK (used_count >= 0),
  success_after    INTEGER NOT NULL DEFAULT 0 CHECK (success_after >= 0),   -- 用过之后下一次独立作答做对的次数
  rating_up        INTEGER NOT NULL DEFAULT 0 CHECK (rating_up >= 0),       -- 学生评价：有用
  rating_down      INTEGER NOT NULL DEFAULT 0 CHECK (rating_down >= 0),     -- 学生评价：没用
  awaiting_outcome INTEGER NOT NULL DEFAULT 0 CHECK (awaiting_outcome IN (0, 1)),   -- 讲完了，等下一次独立作答结果
  last_used_at     TEXT,
  updated_at       TEXT NOT NULL,
  PRIMARY KEY (kp_id, kind),
  CHECK (success_after <= used_count)
) STRICT;

-- 课节摘要：每次学习结束写一行（一次学习 = 打开到关闭工作台），下次打开时接着上次继续
CREATE TABLE sessions (
  id             INTEGER PRIMARY KEY,
  course_id      TEXT NOT NULL,
  session_id     TEXT NOT NULL,           -- 课节 ID，如 S01
  course_version TEXT NOT NULL,
  kp_ids         TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(kp_ids) AND json_type(kp_ids) = 'array'),   -- 所学知识点
  stuck_summary  TEXT,                    -- [仅本地] 仍卡住的地方
  todo           TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(todo) AND json_type(todo) = 'array'),       -- [仅本地] 待办
  next_start     TEXT CHECK (next_start IS NULL OR (json_valid(next_start) AND json_type(next_start) = 'object')),
                                          -- 下次起点 {"page_id", "activity_id"}
  started_at     TEXT NOT NULL,
  ended_at       TEXT
) STRICT;
CREATE INDEX sessions_latest ON sessions (course_id, session_id, started_at);
