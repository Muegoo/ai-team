# RTK, Headroom, Serena, Ponytail และ Caveman

ตรวจวันที่ 18 ตุลาคม 2026 จาก repo/เอกสารปัจจุบันและผลทดสอบปี 2026 ยังไม่ได้ติดตั้งหรือทดสอบกับ Orca ในเครื่อง

ตีความชื่อ “selena” ว่าหมายถึง **Serena (`oraios/serena`)** หากเป็นคนละโปรเจกต์ การประเมินแถวนี้ไม่ครอบคลุมโปรเจกต์นั้น

## ต่างกันที่ชั้นทำงาน

| เครื่องมือ | ชั้นที่เปลี่ยน | ตำแหน่งที่เสนอในทีม |
|---|---|---|
| RTK | กรอง output ของคำสั่งที่รองรับก่อน agent อ่าน | ทดลองกับ Builder/Verifier ที่รัน shell มาก |
| Serena | ค้น reference, อ่านและแก้ code ระดับ symbol ผ่าน MCP/tooling | Scout และ Builder สำหรับ repo ที่ language backend รองรับ |
| Headroom ตัวโปรแกรม | preprocess tool results/context ผ่าน library, proxy หรือ MCP | ทดลองกับ input ขนาดใหญ่และซ้ำมาก |
| Headroom portable skill | สอนนโยบายย่อข้อมูลและเรียก helper scripts | พิจารณาเป็น community skill แยกจากโปรแกรมต้นทาง |
| Ponytail | ลด code/abstraction/dependency ที่งานไม่ต้องการ | Builder หลังได้รับสเปกชัดเจน |
| Caveman ตัว skill | ลดความยาวคำบรรยายที่โมเดลเขียน | รายงาน worker สั้น ๆ; ไม่ใช้บังคับเนื้อหา social/marketing |
| Caveman ชุดโปรแกรมปัจจุบัน | มี compression, model/effort routing และส่วนเสริมอื่นเพิ่มจาก skill | แยกประเมินทีละส่วน ไม่เปิดทั้งหมดพร้อมระบบเดิม |

## Serena

[Repo ต้นทาง](https://github.com/oraios/serena) ระบุความสามารถค้น symbol, reference, outline และแก้ symbol โดยไม่ต้องอ่านทั้งไฟล์ ความสามารถบางส่วนขึ้นกับ language server/backend

จึงเหมาะจะทดลองก่อนสำหรับเป้าหมายอ่านโค้ดให้เร็วและตรงจุด แต่เป็นข้อเสนอจากลักษณะงาน ไม่ใช่ผล benchmark กับ repo ของคุณ งานเล็กใช้ rg/read เดิมอาจเพียงพอ และควรปิด tool ที่ซ้ำกับ harness

ไม่ใช่ตัวบีบอัดทั่วไป ไม่ใช่ตัวจัดการ parallel workers และไม่ต้องเปลี่ยนโมเดล Leader เพื่อใช้ semantic tools

## Headroom

แยก [โปรแกรมต้นทาง](https://github.com/headroomlabs-ai/headroom) กับ [portable skill ของผู้ดูแลอีก repo](https://github.com/romangalaxys10-spec/headroom-skill/blob/main/SKILL.md) ออกจากกัน ความนิยมและ benchmark ของตัวโปรแกรมไม่ใช่หลักฐานประสิทธิภาพของ skill

ตัวโปรแกรมมีการเก็บ original ไว้ให้ retrieve ได้ และมีเส้นทาง wrap สำหรับ coding clients หลายตัว แต่ยังไม่ได้ยืนยัน Orca launch path และ subscription auth แต่ละบัญชีในเครื่องนี้

ข้อจำกัดเชิงกลไก: ถ้าโมเดลได้รับข้อมูลฉบับเต็มแล้วค่อยสั่งให้ย่อ token ที่ใช้รับข้อมูลครั้งแรกก็เกิดไปแล้ว Skill อย่างเดียวไม่ได้ทำให้แก้ประวัติ context ของ client ได้เอง การประหยัด input ครั้งแรกต้องเกิดใน script/tool/proxy ก่อนข้อมูลเข้าโมเดล

เริ่มจาก compression ที่คงข้อมูลเดิมให้เรียกกลับได้ และดูผล cache ร่วมกับ token ดิบ [เอกสาร architecture](https://docs.headroomlabs.ai/docs/architecture) อธิบายโหมด cache ที่รักษาประวัติเดิมกับโหมด token ที่ยอมแลก cache stability บางส่วน การตัด function body เหมาะกับการสำรวจ แต่ต้องเรียก implementation จริงกลับมาก่อนตัดสินใจแก้บั๊ก

อย่าใช้ shared memory/cache ของบริษัทกับส่วนตัวร่วมกันเพียงเพราะใช้เครื่องเดียวกัน

## Ponytail

[Skill ต้นทาง](https://github.com/DietrichGebert/ponytail/blob/main/skills/ponytail/SKILL.md) เน้นเปลี่ยนให้น้อยที่สุดแต่แก้โจทย์ครบ ใช้ของที่มีใน repo ก่อน และไม่ตัด validation/error handling ที่จำเป็น อย่างไรก็ตามโจทย์คลุมเครือจะเอนเข้าหาเวอร์ชันเล็กที่ทำ core job

ข้อเสนอ: Leader ทำ acceptance criteria ให้ชัด แล้วใช้กับ Builder เริ่มจาก lite; ไม่ให้หลัก “ทำเล็ก” ไปกำหนดเป้าหมายทางธุรกิจแทนคุณ และไม่ใช้เป็นกติกาทุก domain

[Benchmark ของผู้ดูแล 7 ตุลาคม 2026](https://github.com/DietrichGebert/ponytail/blob/main/benchmarks/results/2026-10-07-agentic.md) ใช้ 39 งาน งานละ 5 รอบ รายงาน output token ลด 45% และ cost ลด 26% สำหรับ Ponytail 5 เทียบ baseline ข้อจำกัดสำคัญคือปิด Bash ทุก arm จึงไม่ได้วัดวงจร coding/debugging ที่ใช้ shell ครบ และยังเป็นการทดสอบโดยผู้พัฒนาเอง

## Caveman

[Repo ปัจจุบัน](https://github.com/JuliusBrussee/caveman) มีทั้ง skill สำหรับตอบสั้นและชุดโปรแกรมหลายส่วน รวมถึง Auto เลือกโมเดล/effort อย่านำผลทดสอบ skill เก่าไปสรุปถึงทุกส่วนของชุดปัจจุบัน

[JetBrains กรกฎาคม 2026](https://blog.jetbrains.com/ai/2026/07/speak-to-ai-agents-like-cavemen-tosave-tokens/) ทดสอบ Caveman skill กับ Claude Code/Sonnet 5 บน SkillsBench 86 งาน และรายงาน output token ลดราว 8.5% ในการวิเคราะห์คู่เทียบ 82 งาน โดยไม่ตรวจพบความต่างด้านคุณภาพอย่างมีนัยสำคัญ ผลนี้เฉพาะ setup ดังกล่าว ไม่พิสูจน์ว่าไม่มีโอกาสเสียข้อมูลทุกงาน

ข้อเสนอ: ใช้เฉพาะรายงาน worker หากชอบรูปแบบนี้ ให้ Leader อธิบายเป็นภาษาไทยชัดเจน การตัด article ภาษาอังกฤษย่อมไม่ให้ผลแบบเดียวกันโดยอัตโนมัติในภาษาไทย และไม่ควรใช้กับ marketing copy ที่ต้องรักษาน้ำเสียง

ถ้าทดลองชุดโปรแกรม ให้ปิด Auto บน Leader เพื่อรักษา Sol/Opus ตามที่ผู้ใช้กำหนด และไม่ให้ router สองตัวเปลี่ยนโมเดลแข่งกัน

## ปรับคำแนะนำ RTK จากหลักฐานใหม่

[JetBrains กรกฎาคม 2026](https://blog.jetbrains.com/ai/2026/07/rtk-claude-code-token-savings/) ทดสอบ RTK v0.43.0 กับ Claude Code 2.1.201/Sonnet 5 พบ median cost เพิ่ม 7.6% ที่ low effort และประมาณไม่เปลี่ยนที่ high effort โดยคุณภาพไม่ต่างอย่างมีนัยสำคัญ ตัว hook ไม่ได้ครอบคลุมทุก built-in tool และบางงานต้องอ่านหรือเรียกคำสั่งเพิ่ม

ผลนี้ไม่ได้ทดสอบ RTK ทุกเวอร์ชัน ไม่ได้ทดสอบ Codex/Orca หรือทุก workload ข้อเสนอจึงเป็นการทดลองกับงาน shell/log มากก่อน ไม่ถือว่า rtk gain เท่ากับต้นทุนหรือโควตารวมที่ลดจริง

## ลำดับทดลองที่เสนอ

1. เริ่ม baseline เดิม แล้วเพิ่ม Serena ให้ Scout/Builder ใน repo ที่รองรับ
2. ทดลอง Ponytail lite เฉพาะ implementation ที่มี acceptance criteria ชัด
3. เลือก RTK หรือ Headroom มาทดลองทีละตัวจากชนิดข้อมูลที่กิน context จริง
4. Caveman เป็นตัวเลือกด้านรูปแบบรายงาน ไม่ใช่แกนประหยัดหลัก
5. หลังพิสูจน์ทีละตัวแล้วค่อยประกอบ โดยให้ข้อมูลแต่ละชนิดมีผู้กรองหลักหนึ่งตัว ไม่ย่อซ้ำหลายชั้นโดยไม่วัดผล

วัดเวลาไปถึงผลงานที่ผ่านตรวจ, การแก้ซ้ำ, actual usage ที่ client เปิดเผย และ quota observation ภายใน plan เดียวกัน แยก cache read/write และ output เมื่ออ่านได้ ผล % ของเครื่องมือหลายตัวนำมาบวกตรง ๆ ไม่ได้

ทุกเส้นทาง proxy/wrapper ต้องตรวจว่า client ที่ Orca launch ใช้เส้นทางนั้นจริง และยังใช้บัญชี/วิธี billing ที่ตั้งใจไว้ ไม่ถือว่าใช้ได้เพียงเพราะ README ระบุชื่อ Codex หรือ Claude
