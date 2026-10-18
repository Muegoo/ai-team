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

## Benchmark แบบเล็ก

ใช้ input/commit และเงื่อนไขสำเร็จเดียวกัน แยกผลตาม plan/model แล้วบันทึก:

| Case | Setup | Time to accepted result | First-pass pass? | Rework | Available token/usage data | Quota observation | Notes |
|---|---|---|---|---|---|---|---|
| repo discovery | single / team-2 / team-4 | | | | | | |
| bounded feature | single / team-2 / team-4 | | | | | | |
| bug investigation | single / team-2 / team-4 | | | | | | |
| researched content | single / team-2 / team-4 | | | | | | |

ห้ามบวกเปอร์เซ็นต์ quota ของคนละบัญชี/plan เป็นตัวเลข token รวม และหากต้องรันซ้ำเพื่อเทียบควรทำใน workspace ที่แยกจากกัน
