# บันทึกความสามารถ Orca ที่ตรวจในเครื่อง

ตรวจวันที่ 18 ตุลาคม 2026 ด้วยคำสั่งอ่านคู่มือและ help เท่านั้น ไม่ได้ launch worker, สลับบัญชี หรือแก้ settings

Executable ที่ resolve ได้: `orca` → `C:\Users\UsEr\AppData\Local\Programs\orca\resources\bin\orca.exe`

## หลักฐาน

- `orca skills get orchestration`: คู่มือ runtime แยก Run / Task / Dispatch, ระบุ task contract และวงจร inbox → settle → reuse/retain/release
- `orca skills get orchestration --reference references/coordinator-loop.md`: เริ่ม ready wave ก่อน wait; ใช้ `--model` / `--effort` เมื่อรองรับ; ตรวจ `launch.requested` เทียบ `launch.effective`
- `orca orchestration worker-start --help`: รองรับ `--agent`, `--model`, `--effort`, `--task` หรือ `--spec`, `--deps`, `--worktree`, `--terminal`, `--run`; `--effort` ต้องมี `--model`; ไม่ใช้ model override กับการ reuse `--terminal`
- `orca agent launch --help`: เลือก agent/provider, model และ effort ได้ใน workspace เดิม
- `orca account list --help`: build นี้อธิบาย filter สำหรับ `opencode|devin`; ไม่ใช้เป็นหลักฐานว่าระบุบัญชี Codex/Claude ต่อ worker ได้
- `orca --help`: มี `account add` สำหรับ Claude/Codex ใน common commands แต่ไม่มี account selector ใน synopsis ของ `worker-start`/`agent launch` ที่ตรวจ จึงยังต้องยืนยันเส้นทางเลือกบัญชีจริงจาก build/UI/schema ที่เกี่ยวข้องก่อนลงมือ
- `orca skills get orca-cli`: คู่มือการใช้ worktree/terminal; folder workspace ใช้ได้; browser ภายใน Orca ต้องใช้คู่มือ browser ของ Orca

คำสั่ง help/guide คืน exit code 0 พร้อม stderr จาก Crashpad ว่า `CreateFile: Access is denied. (0x5)` การอ่านคู่มือยังสำเร็จ แต่ยังไม่ได้ทดสอบ runtime launch หรือระบบ account routing จึงไม่อ้างว่าทำงานครบ end-to-end

## ตัวอย่างคำสั่งสำหรับขั้นนำไปใช้งาน

เป็นตัวอย่างสำหรับ coordinator ที่อ่านคู่มือปัจจุบันแล้ว ไม่ใช่สคริปต์ติดตั้งหรือขั้นตอนครบวงจร และยังไม่ได้รันคำสั่งด้านล่าง

```powershell
orca status --json
orca orchestration run-create --objective "งานที่มีขอบเขตและเกณฑ์สำเร็จชัดเจน" --json
orca orchestration worker-start --spec "Scout-A: อ่านเฉพาะโมดูล A และส่งหลักฐานตาม contract" --worktree current --agent codex --model gpt-6-luna --effort low --json
orca orchestration worker-start --spec "Scout-B: อ่านเฉพาะโมดูล B และส่งหลักฐานตาม contract" --worktree current --agent codex --model gpt-6-luna --effort low --json
```

เลือกโมเดลตามสิทธิ์บัญชีจริง ตรวจ launch receipt และทำวงจร wait/รับผล/cleanup ให้ครบตามคู่มือ อย่าใช้สองคำสั่งนี้เป็นหลักฐานว่า worker ใช้คนละบัญชี และอย่าใช้ `current` สำหรับ worker ที่แก้ไฟล์ชุดเดียวกันโดยไม่มี ownership

การนำแบบนี้ไปบังคับใช้จริงยังต้องตรวจ account identity, model availability, sandbox/tool permissions และทดสอบงานขนาดเล็กหนึ่งรอบ ไม่จำเป็นต้องซื้อ API เพื่อเริ่มทดลองแบบหนึ่งบัญชี
