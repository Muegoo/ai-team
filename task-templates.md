# แม่แบบ task และผลส่งกลับ

ตัวอย่างต่อไปนี้เป็นรูปแบบเอกสารที่เสนอ ไม่ใช่ schema หรือ config ของ Orca ไม่ใส่ credentials ในไฟล์นี้

สำหรับการตีความตัวอย่าง/การตรวจ defect class ให้ใช้ [นโยบาย Example-based defect coverage ใน ai-team-routing](.agents/skills/ai-team-routing/SKILL.md#example-based-defect-coverage)

## Brief ที่ Leader เก็บไว้

```yaml
goal: "เพิ่มระบบ subscription ตาม requirement ที่ตกลง"
data_boundary: company
acceptance:
  - "สถานะสมาชิกตรงกับ event ที่ตรวจลายเซ็นแล้ว"
  - "event ซ้ำไม่ทำให้สถานะผิด"
  - "integration tests ผ่านบน changes ที่รวมแล้ว"
reported_examples: []
suspected_defect_class: "กลไกร่วมที่คาดว่าเป็นต้นเหตุ"
related_scope: "พื้นผิวที่อนุญาตให้ตรวจเพิ่ม"
scope_boundary: "ระบุเมื่อผู้ใช้จำกัดขอบเขตอย่างชัดเจน"
constraints:
  - "ใช้ provider และ stack เดิม"
decisions_file: "artifacts/subscription/decisions.md"
contract_file: "artifacts/subscription/contract.md"
active_worker_cap: 3
account_route: "verified company-approved profile"
```

## Scout task

```text
Target: backend billing module และจุดเรียกใช้โดยตรง
Question: lifecycle ของ subscription เก็บและเปลี่ยนสถานะตรงไหน?
Defect class / related scope: ใช้ขอบเขตจาก Leader; ดูนโยบาย coverage ใน ai-team-routing
Reported examples: ตัวอย่างจากผู้ใช้ที่ต้องตรวจกรณีเพิ่มเติม
Inputs: brief และ path ที่เกี่ยวข้อง; ค้น symbol ก่อนอ่าน
Ownership: อ่าน source; เขียนได้เฉพาะ artifacts/subscription/scout-backend.md
Exclusions: ห้ามแก้ production code และไม่ scan frontend ซ้ำกับ Scout-B
Acceptance: ระบุ entry points, invariants, path:line, test ที่มี และส่วนที่ยังไม่ตรวจ
Additional findings / counterexamples: หลักฐานนอกตัวอย่างและขอบเขตที่พบ (ถ้ามี)
Coverage: inspected / uninspected พร้อมข้อจำกัด
Output: สรุปประมาณ 300–700 token; รายละเอียดเก็บใน artifact
Model preference: Luna; ขอ Leader ยกระดับเมื่อพบตรรกะที่ยังสรุปไม่ได้
Soft checkpoint: เมื่อเกินเวลาที่ตกลงหรือพบข้อมูลไม่พอ ให้คืนสิ่งที่รู้พร้อม blocker
```

## Builder task

```text
Target: src/billing/** ตาม contract ที่ระบุ
Change: implement webhook handler และ idempotent state update
Defect class / related scope: ใช้ขอบเขตที่ Leader อนุมัติและผล Scout
Inputs: brief, contract และ scout artifact เฉพาะส่วนนี้
Ownership: src/billing/** และ tests/billing/**
Do not touch: frontend, lockfile, global config, shared schema ที่มีเจ้าของอื่น
Dependencies: contract ต้องพร้อมก่อนเริ่ม implementation
Acceptance: test ที่ตรวจ signed event, duplicate event และ invalid event ผ่าน
Coverage evidence: กลไกร่วมและรูปแบบข้อมูลที่เกี่ยวข้องซึ่งตรวจแล้ว; ระบุ counterexamples หรือส่วนที่ยังไม่ตรวจเมื่อมี
Output: diff/artifact path, ไฟล์ที่แก้, คำสั่งตรวจและ exit code, ข้อจำกัด
Escalation: ถ้าต้องเปลี่ยน shared schema ให้ส่งคำขอกลับ Leader ก่อนแก้
```

## Research task

```text
Question: เปรียบเทียบสินค้า 3 รายการสำหรับกลุ่มเป้าหมายที่กำหนด
Scope: คุณสมบัติที่มีผลต่อการตัดสินใจ พร้อมข้อมูลปัจจุบันจากผู้ผลิต
Constraints: ไม่แต่งราคา เงื่อนไข affiliate หรือประสบการณ์ใช้จริง
Ownership: artifacts/affiliate/product-facts.md
Acceptance: ทุก claim สำคัญมี URL, วันที่เผยแพร่หรือ accessed date, และข้อจำกัด
Output: fact sheet สั้น พร้อมข้อขัดแย้ง/ข้อมูลที่ยังหาไม่ได้
```

## Result ที่ worker ส่งกลับ

```yaml
task_id: "ใช้ ID จริงจาก runtime เมื่อมี"
dispatch_id: "ใช้ ID จริงจาก runtime เมื่อมี"
outcome: succeeded # หรือ failed; เป็นตัวอย่างข้อความ ไม่ใช่ lifecycle event
summary: "ผลที่ทำได้ 2–3 ประโยค"
artifacts:
  - "path ไปผลเต็ม"
evidence:
  - "คำสั่งตรวจ + exit code + path log หรือ URL + date"
coverage: "ขอบเขตที่ตรวจจริง"
uninspected: "ส่วนที่ยังไม่ตรวจ"
additional_findings: "กรณีเพิ่มเติมที่มีหลักฐานและ counterexamples/boundaries ถ้ามี"
risks: []
next_action: "ผู้รับช่วงหรือการตัดสินใจที่ต้องการ"
```

การส่งไฟล์ YAML นี้ไม่แทน `worker_done` ของ Orca worker ต้องส่ง lifecycle event จริงตาม injected preamble และคู่มือ runtime

## Checkpoint สำหรับข้าม session/บัญชีที่อนุญาต

```text
Goal and current acceptance criteria:
Data boundary and authorized destination:
Workspace/base commit or current artifact version:
Decisions and rationale:
Completed tasks with evidence:
Remaining tasks and dependencies:
Failed attempts and what they ruled out:
Files owned by each active worker:
Open risks and latest user corrections:
Exact next action and owner:
```

## Controlled pilot

รัน pilot แบบ paired 6–10 งานจริง โดยแต่ละงานมี deliverable และ acceptance criteria เดียวกันในทุก mode:

- `baseline`: controller และ executor ที่อนุมัติ 1 คน; controller ไม่เขียน code
- `team-2`: controller และ executor ที่อนุมัติ 2 คน
- `team-4`: controller และ executor ที่อนุมัติ 4 คน เฉพาะเมื่อการทดลองนี้มีความจำเป็นและ runtime อนุญาต

คง model/effort และ input/acceptance criteria ให้เทียบกันได้ในแต่ละคู่ บันทึกรุ่นและข้อจำกัดที่ตรวจได้ สุ่มหรือ counterbalance ลำดับ mode ระหว่างงาน จัดหนึ่ง writable agent ต่อ worktree และบันทึก routing receipt กับสถานะ authorization ต่อ task โดยไม่มี secret ทุก task ต้องผ่าน application acceptance tests ตามเกณฑ์และ controller final review จึงนับเป็น `accepted`; เก็บหลักฐานการตัดสินนั้นด้วย

หนึ่งแถวต่อหนึ่ง deliverable รวม retries ทั้งหมด `rework_count` คือจำนวนรอบซ่อมเพิ่มเติม ใช้เวลาและ usage ของทุกสถานะรวมทั้ง rejected/blocked คิดต้นทุนต่อ accepted result บันทึกเวลาโหลด skill, การตัดสินใจใช้ tool และ rework ด้วย Usage ที่อ่านไม่ได้ต้องเป็น `null`/unknown ไม่ใช่ศูนย์ ห้ามอนุมานต้นทุน subscription จากราคา API และห้ามรวม quota ข้ามบัญชี First smoke tests เป็น functional checks ไม่ใช่หลักฐานวัดความเร็วหรือต้นทุนของทีม

### Lifecycle smoke test

ก่อน dispatch ให้ตรวจ `orca status --json` และอ่าน orchestration guide ที่ตรงกับ runtime version ที่ติดตั้ง จากนั้นทำ task อ่านอย่างเดียวหนึ่งงานที่ได้รับอนุญาต ตรวจ launch receipt ว่า `launch.requested` และ `launch.effective` ตรงกับ controller/executor และ model/effort ที่ตั้งใจ เมื่อทำงานเสร็จ worker ส่ง `worker_done` ด้วย outcome `succeeded` ตาม preamble; controller รับและตรวจผล, acknowledge และ release worker ตาม runtime แล้วตรวจว่าไม่มี worker ที่ยัง reclaim ได้ จึงนับว่า smoke test สำเร็จ

ถ้าเจอ usage/quota limit, sandbox denial หรือส่ง lifecycle event ไม่สำเร็จ ให้บันทึกเป็น blocked/failed ตามข้อเท็จจริง ห้ามนับว่าสำเร็จ ห้าม auto-retry หรือเปลี่ยนบัญชีเอง

### CLI และ schema

สำหรับ skill inventory, contract-to-ticket briefs, comparative validation และ reviewed lessons ดู [Local engineering practices](practices.md) ส่วนการเลือกงานที่ทำพร้อมกันอย่างจำกัด ใช้ [Workflow CLI](workflow.md) ซึ่งสร้างแผนจาก `worktree_id`, writable paths, dependencies และ acceptance ที่ controller ระบุเอง; ไม่ได้ dispatch worker อัตโนมัติ ใช้ `wait` อ่าน Orca receipts โดยไม่ ACK และใช้ `usage` เฉพาะ log ที่ระบุชัดเจน ดู schema และข้อจำกัดการตีความใน `workflow.md`

ตรวจ executable presence โดยไม่อ่าน config หรือ environment และรวมผลจาก JSON array ด้วยคำสั่งต่อไปนี้:

```sh
python3 scripts/pilot.py preflight
python3 scripts/pilot.py summarize PATH
python3 -m unittest discover -s tests -p 'test_*.py'
```

`preflight` แสดง boolean ของ executable ที่ตรวจเท่านั้น; authentication และ model entitlement แสดง `unknown` เสมอ การพบ executable ไม่อนุญาตให้ launch wrapper หรือ agent

แต่ละ JSON object ต้องมี `task_id` (string ไม่ว่าง), `mode` (`baseline`, `team-2`, `team-4`), `status` (`accepted`, `rejected`, `blocked`), `elapsed_seconds` (finite number ไม่ติดลบ) และ `rework_count` (integer ไม่ติดลบ) ฟิลด์เสริม `cost_usd` (finite number ไม่ติดลบ) และ `tokens` (integer ไม่ติดลบ) รับ `null` เมื่อไม่มีข้อมูล ระเบียนซ้ำสำหรับคู่ `task_id`/`mode` และ input ว่างไม่ผ่าน validation

ผลสรุปนับสถานะ, accepted/total, first-pass rate (accepted ที่ไม่มี rework หารด้วยงานทั้งหมด), elapsed รวมทุกสถานะ, seconds per accepted (null เมื่อไม่มี accepted), และ rework รวม `cost_usd`/`tokens` ต่อ accepted คำนวณได้เมื่อทุกแถวใน mode นั้นมี metric และมี accepted อย่างน้อยหนึ่งงาน; ผลมี `measured_count` coverage และ `null` เมื่อข้อมูลไม่ครบ ผลจากชุดสังเคราะห์สำหรับทดสอบ CLI ไม่ใช่ benchmark result และห้ามบันทึกเป็นผลการทดลองจริง

### Comparative pilot validation

สถานะ: **เครื่องมือตรวจความครบของคู่ implement แล้ว; ยังไม่ได้รัน paired coding pilot จริง** ใช้ `python3 scripts/pilot.py summarize PATH --compare baseline team-2` เพื่อกำหนดอย่างน้อยสอง mode ที่ไม่ซ้ำและบังคับให้ทุก task ID ใน input มี record ในแต่ละ mode ที่เลือก หากข้อมูลไม่ครบ CLI แสดงคู่ task/mode ที่ขาดและไม่เขียน stdout; แถวของ mode อื่นยังอยู่ในผล aggregate ปกติ ส่วน metadata comparison ระบุเฉพาะ mode ที่เลือกและจำนวน task ที่ครบ

ก่อนนำผลไปเปรียบเทียบ controller ต้องคุม start commit, inputs, model/effort และ acceptance criteria ให้เทียบกันได้ภายในแต่ละคู่ บันทึก routing receipt และสถานะ authorization โดยไม่มี secret งาน `baseline` ใช้ controller กับ executor ที่อนุมัติหนึ่งคน; `team-2` ใน pilot ขั้นแรกใช้ Luna เขียน tests แล้วหยุด ก่อนส่งงานใน worktree เดิมให้ Luna อีกคน implement ตามลำดับ จึงห้ามอ้างประโยชน์ด้านความเร็วจากการทำงานขนาน ใช้ worktree และ session ใหม่แยกต่อ mode และป้องกันไม่ให้คำตอบหรือ diff ข้าม mode

`--compare` ตรวจความครบของ task/mode เท่านั้น ไม่รับรองว่า inputs, models, bases หรือ acceptance เหมือนกัน และไม่พิสูจน์เหตุและผล งานจริงหนึ่งคู่ไม่พอพิสูจน์การประหยัด; ทำ paired task จริงหลายงานและ counterbalance ลำดับ mode ก่อนสรุปผล ตัวอย่างใน `examples/practices/pilot-*.synthetic.json` เป็นข้อมูลสังเคราะห์เท่านั้น ห้ามนับเป็น benchmark หรือ commit ตัวเลขผลทดลองที่ไม่มีจริง Usage ที่อ่านไม่ได้เก็บเป็น `null`/unknown.
