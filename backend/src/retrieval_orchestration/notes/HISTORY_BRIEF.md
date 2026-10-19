# Lưu lịch sử chat JSON sau khi kết thúc

User yêu cầu lưu phiên chat vào1fileJSON. Chỉ sửa hoi.py và tests/test_chat_history.py.
Không sửa retrieval_flow modules hoặc các test khác; không network/DB/install/git.
Product được phép ghi chat_history/ trong folder này (user đã cho phép).

Upstream: ChatSession() có session_id UUID, async ask(text)->dict envelope FIXTURE,
last_result property ->dict|None, reset(). render_response(result)->str tiếng Việt.
Các module upstream thật được stage nguyên byte cho import/runtime, không sửa/stub.
Current hoi.main async noargs giữ1session, /moi reset, /json debug, exit/quit/thoat/thoát
thoát, blankskip, EOFError/KeyboardInterrupt kết thúc. Giữ mọi hành vi đó.

Implement save_history(history:dict,directory:Path|None=None)->Path. Default path
Path(__file__).resolve().parent/'chat_history'; không phụ thuộc cwd hay usertext.
mkdir khi lưu. Mỗi lần gọi tạo tên file riêng timestamp+uuid để không ghi đè.
UTF8 JSON indent2 ensure_asciiFalse, nội dung roundtrip nguyênhistory. Không tự thêm
field trong save_history; caller chuẩn bịdocument. Không dùng tên/path từ câu hỏi.

main(*,persist:bool=False,history_dir:Path|None=None)->dict: defaultFalse để các
test hiện tại gọi main() không tạo lịch sử chat giả trong folder người dùng.
__main__ thực sự phải asyncio.run(main(persist=True)). CLI vẫn một lệnh cũ.
main tạo document schema_version1.0,session_id,started_at,saved_at,messages.
Messages list role user/assistant,content text,timestampUTC; assistant thêm result
dict envelope. Giữ đúng thứ tự từng câu user và phản hồi hiển thị; không chỉ lưu
last_result. /moi ghi nhận command hoặc message reset trong transcript, xóa memory
nhưng không xóa các lượt đã chat. /json không chạy lại retrieval. Không cần ghi
blank hoặcexit. Khi session không có messages thì không tạo file rỗng.
Ghi trong finally khi persistTrue và cómessages, cả exit/EOF/Ctrl+C và caller
cancellation trong lúc ask; giữ cả user message chưa kịp có response. Không nuốt
cancellation hoặc exception ngoài dự kiến; finally chỉ bảo đảm thử lưu lịch sử.
Thông báo đường dẫn sau khi ghi thành công, OSError ghi báo lỗi rõ và không báo
lưu thành công. Có thể catchOSError in thông báo ngắn, không che lỗi khác.
Không đọc/load lại file hoặc phục hồi memory khi mở lại; task chỉ lưu để xem.
Không sửa/filepublish/autogitignore ngoàiallowlist. Keep implementation compact.

Test meaningful: Unicode JSONroundtrip,2saves distinct files, path stable when cwd
changes via mock ifneeded; actual CLI main persistTrue with mocked input and temp
directory inside candidate .agent-state. Verify ordered multipleturns/results and
schema,timestamps; exit/EOF/Ctrl+C, emptynofile, OSError feedback, defaultmain no disk.
Test body may create temporaryfiles only under Path(__file__).resolve().parents[1]/'.agent-state'.
No network/subprocess arbitrary commands from tests. No coverage claim unmeasured.
Output exactmanagerJSON, no narrative/fences/undeclared files. Only2editablefiles.
