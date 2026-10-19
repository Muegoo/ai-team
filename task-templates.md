# แม่แบบ task และผลส่งกลับ

ตัวอย่างต่อไปนี้เป็นรูปแบบเอกสารที่เสนอ ไม่ใช่ schema หรือ config ของ Orca ไม่ใส่ credentials ในไฟล์นี้

## Brief ที่ Leader เก็บไว้

```yaml
goal: "เพิ่มระบบ subscription ตาม requirement ที่ตกลง"
data_boundary: company
acceptance:
  - "สถานะสมาชิกตรงกับ event ที่ตรวจลายเซ็นแล้ว"
  - "event ซ้ำไม่ทำให้สถานะผิด"
  - "integration tests ผ่านบน changes ที่รวมแล้ว"
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
Inputs: brief และ path ที่เกี่ยวข้อง; ค้น symbol ก่อนอ่าน
Ownership: อ่าน source; เขียนได้เฉพาะ artifacts/subscription/scout-backend.md
Exclusions: ห้ามแก้ production code และไม่ scan frontend ซ้ำกับ Scout-B
Acceptance: ระบุ entry points, invariants, path:line, test ที่มี และส่วนที่ยังไม่ตรวจ
Output: สรุปประมาณ 300–700 token; รายละเอียดเก็บใน artifact
Model preference: Luna; ขอ Leader ยกระดับเมื่อพบตรรกะที่ยังสรุปไม่ได้
Soft checkpoint: เมื่อเกินเวลาที่ตกลงหรือพบข้อมูลไม่พอ ให้คืนสิ่งที่รู้พร้อม blocker
```

## Builder task

```text
Target: src/billing/** ตาม contract ที่ระบุ
Change: implement webhook handler และ idempotent state update
Inputs: brief, contract และ scout artifact เฉพาะส่วนนี้
Ownership: src/billing/** และ tests/billing/**
Do not touch: frontend, lockfile, global config, shared schema ที่มีเจ้าของอื่น
Dependencies: contract ต้องพร้อมก่อนเริ่ม implementation
Acceptance: test ที่ตรวจ signed event, duplicate event และ invalid event ผ่าน
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

ตรวจ executable presence โดยไม่อ่าน config หรือ environment และรวมผลจาก JSON array ด้วยคำสั่งต่อไปนี้:

```sh
python3 scripts/pilot.py preflight
python3 scripts/pilot.py summarize PATH
python3 -m unittest discover -s tests -p 'test_*.py'
```

`preflight` แสดง boolean ของ executable ที่ตรวจเท่านั้น; authentication และ model entitlement แสดง `unknown` เสมอ การพบ executable ไม่อนุญาตให้ launch wrapper หรือ agent

แต่ละ JSON object ต้องมี `task_id` (string ไม่ว่าง), `mode` (`baseline`, `team-2`, `team-4`), `status` (`accepted`, `rejected`, `blocked`), `elapsed_seconds` (finite number ไม่ติดลบ) และ `rework_count` (integer ไม่ติดลบ) ฟิลด์เสริม `cost_usd` (finite number ไม่ติดลบ) และ `tokens` (integer ไม่ติดลบ) รับ `null` เมื่อไม่มีข้อมูล ระเบียนซ้ำสำหรับคู่ `task_id`/`mode` และ input ว่างไม่ผ่าน validation

ผลสรุปนับสถานะ, accepted/total, first-pass rate (accepted ที่ไม่มี rework หารด้วยงานทั้งหมด), elapsed รวมทุกสถานะ, seconds per accepted (null เมื่อไม่มี accepted), และ rework รวม `cost_usd`/`tokens` ต่อ accepted คำนวณได้เมื่อทุกแถวใน mode นั้นมี metric และมี accepted อย่างน้อยหนึ่งงาน; ผลมี `measured_count` coverage และ `null` เมื่อข้อมูลไม่ครบ ผลจากชุดสังเคราะห์สำหรับทดสอบ CLI ไม่ใช่ benchmark result และห้ามบันทึกเป็นผลการทดลองจริง

### งานทดลองแรก: ตรวจว่าคู่ baseline/team-2 ครบก่อนเปรียบเทียบ

สถานะ: **งานที่รอทำ ยังไม่ได้ implement** ขณะนี้ CLI ตรวจ duplicate และ validation ภายในแต่ละระเบียน แต่ยังไม่ตรวจว่าทุก task มีทั้ง `baseline` และ `team-2`; ห้ามถือผลสรุปปัจจุบันว่าเป็นการตรวจความครบของคู่ทดลอง

**การเปรียบเทียบที่อนุมัติสำหรับงานนี้:** controller กำหนด mode เป็น `baseline` กับ `team-2` ใช้ start commit, inputs, model/effort และ acceptance criteria เดียวกันภายในแต่ละคู่ งาน `baseline` ให้ Luna หนึ่งคน implement พร้อม tests ส่วน `team-2` ให้ Luna คนหนึ่งเขียน tests ก่อนแล้วหยุด จากนั้นส่งต่องานใน worktree เดิมให้ Luna อีกคน implement หลังผู้เขียน tests หยุดแล้ว การส่งต่อทำตามลำดับ จึงห้ามอ้างประโยชน์ด้านความเร็วจากการทำงานขนาน ใช้ worktree ใหม่และ session ใหม่ที่สะอาดแยกกันสำหรับแต่ละ mode และป้องกันไม่ให้คำตอบหรือ diff จากอีก mode รั่วเข้าไป

**Acceptance criteria:**

- เพิ่ม opt-in comparative validation ใน `scripts/pilot.py` (เสนอ flag `--compare baseline team-2`) ให้ตรวจทุก task ว่ามี record ของทั้งสอง mode ครบก่อนแสดงผลเปรียบเทียบ; `summarize` ปกติยังคงสรุป mode เดียวหรือหลาย mode ที่มีอยู่ได้ตามเดิม
- เมื่อเปิด comparison แล้วขาดคู่ ให้คืน error ที่ระบุ task และ mode ที่หายไป; คู่ที่ครบสรุปได้ และงานที่ input มี task/mode ขาด record ต้องไม่ผ่าน comparative validation
- ยังคงปฏิเสธ duplicate task/mode, mode ที่ไม่รองรับ และข้อมูล invalid ตามเดิม
- เพิ่มกรณีทดสอบคู่ครบ, task/mode ที่ขาด, duplicate และ invalid; tests เดิมทั้ง 9 รายการยังผ่าน
- บันทึก routing receipt, elapsed time, rework count และ usage โดยเก็บ usage ที่อ่านไม่ได้เป็น unknown/null

เก็บ task metadata และ receipts เป็น sidecar ใน local runtime; อย่า commit ผลตัวเลขหรือข้อมูลทดลองที่ยังไม่มีจริง งานทดลองหนึ่งคู่ยังพิสูจน์การประหยัดไม่ได้ ให้ทำหลาย task จริงและ counterbalance ลำดับ mode ก่อนสรุปผล
