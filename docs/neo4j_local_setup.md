# Hướng dẫn cài và chạy Neo4j local cho FinMind

Hướng dẫn dành cho Windows và PowerShell, theo cấu hình repo ngày 18/09/2026. Mục tiêu là chạy Neo4j Community bằng Docker, nhận JSON normalized và nạp thành Knowledge Graph.

Phần crawler do nhóm data quản lý. Bạn không cần chạy crawler để thử graph với các file đã có trong `data/normalized`.

## 1. Cần cài những gì?

| Thành phần | Công dụng |
| --- | --- |
| Python >= 3.10 | Chạy contract, adapter và CLI ingestion |
| Docker Desktop, backend WSL 2 | Chạy container Neo4j trên Windows |
| Git | Lấy repo nếu máy chưa có |
| Trình duyệt | Mở Neo4j Browser để truy vấn và xem graph |

Không cần cài Java riêng vì image Neo4j đã có môi trường chạy. Tài khoản Docker và tài khoản Aura không phải tài khoản đăng nhập database local.

Docker Desktop có điều kiện miễn phí cho cá nhân và giáo dục; xem [điều kiện sử dụng](https://docs.docker.com/subscription-billing/desktop-license/). Neo4j chạy ở đây là Community, không phải Enterprise trial. Các cổng database chỉ mở trên localhost theo [docker-compose.yml](../docker-compose.yml).

## 2. Chuẩn bị WSL và Docker Desktop

Nếu Docker đã chạy và lệnh `docker version` có phần Server, bỏ qua bước cài này.

### 2.1. Kiểm tra ảo hóa

Mở **Task Manager → Performance → CPU**, tìm `Virtualization`.

- `Enabled`: đã bật ảo hóa ở firmware.
- `Disabled`: bật Intel Virtualization Technology / VT-x hoặc AMD SVM / AMD-V trong BIOS/UEFI. Vị trí tùy máy; tham khảo hướng dẫn của nhà sản xuất.

Docker WSL 2 cần ảo hóa phần cứng, tối thiểu 8 GB RAM và phiên bản Windows được Docker hỗ trợ. Kiểm tra [yêu cầu hệ thống Docker](https://docs.docker.com/desktop/setup/install/windows-install/) trước khi cài.

### 2.2. Cài hoặc cập nhật WSL

Mở Start, tìm PowerShell, chọn **Run as administrator**. Với máy chưa có WSL, chạy:

```powershell
wsl --install --no-distribution
```

Lưu công việc và khởi động lại Windows nếu được yêu cầu. Sau đó mở PowerShell Administrator và chạy:

```powershell
wsl --update
wsl --set-default-version 2
wsl --version
```

Docker yêu cầu WSL 2.1.5 trở lên cho backend này. Nếu WSL đã có, thường chỉ cần update và kiểm tra version. Xem [hướng dẫn WSL của Microsoft](https://learn.microsoft.com/en-us/windows/wsl/install).

### 2.3. Cài Docker Desktop

1. Tải bản Windows phù hợp CPU từ [trang cài Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/).
2. Cài và chọn backend WSL 2 nếu trình cài đặt hỏi.
3. Khởi động lại máy nếu được yêu cầu.
4. Mở Docker Desktop và chờ Engine chạy.

Trong PowerShell thường, kiểm tra:

```powershell
docker version
docker compose version
```

`docker version` phải có cả **Client** và **Server**. Chỉ có Client hoặc báo không kết nối được daemon nghĩa là Engine chưa sẵn sàng. Đăng nhập tài khoản Docker thành công chưa chứng minh Engine đã chạy.

## 3. Mở repo và xác nhận branch

Nếu chưa có repo, clone nhánh `nhan`:

```powershell
git clone --branch nhan https://github.com/minhquan9125/FinMind.git
cd FinMind
```

Nếu đã có repo trên máy hiện tại:

```powershell
cd C:\Users\GamingGear\Desktop\FinMind\FinMind
```

Nếu máy khác, thay đường dẫn bằng thư mục chứa repo của bạn.

Kiểm tra:

```powershell
git status --short --branch
git branch --show-current
```

Branch phát triển phần graph là `nhan`. Các lệnh Compose và Python phía dưới được chạy từ **thư mục gốc repo**, nơi có `docker-compose.yml`, `backend` và `data`.

Hướng dẫn này cần phiên bản repo đã có cấu hình Neo4j trong `docker-compose.yml`; file trống ở phiên bản cũ không chạy được Compose service `neo4j`.

## 4. Chuẩn bị môi trường Python

Kiểm tra Python:

```powershell
py --version
```

Cần phiên bản >= 3.10. Nếu chưa cài, cài Python từ [python.org](https://www.python.org/downloads/windows/) rồi mở terminal mới.

Repo dùng virtual environment chung `$HOME\.venv`. Tạo nếu chưa có:

```powershell
if (-not (Test-Path "$HOME\.venv\Scripts\python.exe")) {
    py -m venv "$HOME\.venv"
}
```

Kích hoạt và cài thư viện:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& "$HOME\.venv\Scripts\Activate.ps1"
python --version
python -m pip install -r backend/requirements.txt
```

Execution policy chỉ thay đổi trong process terminal hiện tại. Nếu environment đã có nhưng Python bên trong quá cũ hoặc không chạy được, cần sửa môi trường trước khi tiếp tục.

Không dùng `backend/venv` được lưu trong repo: trên máy đã kiểm chứng, môi trường đó trỏ tới Python của máy khác.

Các dependency backend hiện tại là Neo4j official driver và `python-dotenv`.

## 5. Cấu hình `.env` một lần

File dùng chung cho CLI và Docker Compose là **`.env` ở thư mục gốc repo**, không phải `backend/.env`.

Nếu chưa có file, tạo từ mẫu mà không ghi đè cấu hình đã có:

```powershell
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
notepad .env
```

Điền cấu hình local:

```dotenv
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD='YOUR_LOCAL_PASSWORD_AT_LEAST_8_CHARACTERS'
NEO4J_DATABASE=neo4j
```

Thay placeholder password bằng mật khẩu riêng của bạn, ít nhất tám ký tự. Để tránh khác biệt giữa cách Compose và Python xử lý escape/interpolation, nên dùng mật khẩu dài tạo ngẫu nhiên từ chữ, số, dấu `-` và `_`.

CLI chấp nhận `NEO4J_USERNAME` như tên thay thế, nhưng mẫu ưu tiên `NEO4J_USER`. Database local dùng username/database `neo4j`, không dùng instance ID Aura.

File `.env` được ignore và không upload GitHub. Không gửi mật khẩu vào chat hoặc đưa mật khẩu thật vào `.env.example`.

Biến môi trường đã đặt trong terminal được ưu tiên hơn file. Nếu trước đó đã cấu hình Aura qua `$env:...`, hãy mở terminal mới; hoặc xóa riêng các biến kết nối của process hiện tại trước khi chạy local:

```powershell
Remove-Item Env:NEO4J_URI, Env:NEO4J_USER, Env:NEO4J_USERNAME, Env:NEO4J_PASSWORD, Env:NEO4J_DATABASE -ErrorAction SilentlyContinue
```

Lệnh này không xóa file `.env`. Nếu cấu hình được đặt cố định trong môi trường Windows thì cần điều chỉnh ở Windows Environment Variables nữa.

Trong lần setup tự động trên máy hiện tại, cấu hình Aura đã được sao lưu vào `.env.aura.backup`, cũng được ignore. File backup không được code tự đọc.

## 6. Khởi động Neo4j

Docker Desktop phải đang chạy. Từ thư mục gốc repo:

```powershell
docker compose config --quiet
docker compose up -d --wait --wait-timeout 300 neo4j
docker compose ps
```

`config --quiet` kiểm tra cấu hình mà không in credentials. Không chạy `docker compose config` rồi chia sẻ toàn bộ output, vì cấu hình đã resolve có thể chứa mật khẩu.

Lần đầu Docker tải image `neo4j:2026.08.1`; có thể mất vài phút tùy mạng và máy. Kết quả mong đợi của `ps` là service `neo4j` ở trạng thái `Up ... (healthy)`.

| Cổng | Công dụng |
| --- | --- |
| `http://localhost:7474` | Neo4j Browser |
| `bolt://localhost:7687` | Kết nối database cho Python và Browser |

Healthcheck chỉ kiểm tra cổng Bolt đã mở. Nó không thay thế kiểm tra username/password hoặc một truy vấn thành công.

Neo4j dùng named volume `neo4j_data` để lưu database; Docker Compose thêm prefix project vào tên volume thực tế. Mật khẩu trong `.env` đặt mật khẩu ban đầu cho database mới. Thay `.env` không tự đổi mật khẩu của database đã có trong volume. Xem [hướng dẫn Neo4j Docker](https://neo4j.com/docs/operations-manual/current/docker/introduction/).

## 7. Đăng nhập Neo4j Browser

Mở [http://localhost:7474](http://localhost:7474), rồi kết nối bằng:

| Trường | Giá trị |
| --- | --- |
| Connect URL | `bolt://localhost:7687` |
| Database, nếu có trường chọn | `neo4j` |
| Username | `neo4j` |
| Password | Giá trị `NEO4J_PASSWORD` trong `.env` |

Nhập riêng lệnh Browser để chọn database:

```text
:use neo4j
```

Sau đó chạy một truy vấn khác:

```cypher
RETURN 'FinMind connected' AS message;
```

Các lệnh `:use` được nhập trong Browser, không phải PowerShell. `neo4j` là database dữ liệu; `system` dùng quản trị. Xem [lệnh Neo4j Browser](https://neo4j.com/docs/browser/reference-commands/).

## 8. Kiểm tra JSON bằng dry-run

Trong PowerShell đã kích hoạt môi trường Python:

```powershell
python -B -m backend.src.graph.ingest --dry-run --input data/normalized/FPT.json
```

Dry-run đọc JSON, kiểm tra contract và tạo cấu trúc graph trong bộ nhớ; không kết nối hoặc ghi Neo4j. Nó cũng không đọc credentials từ `.env`.

Với file FPT phiên bản `20260915T093340Z`, kết quả đã kiểm chứng:

| Loại bản ghi | Số lượng |
| --- | ---: |
| ReportingPeriod | 42 |
| FinancialReport | 167 |
| Metric | 790 |
| Observation | 33.127 |
| PriceBar | 2.167 |

Counts không gồm Company và Dataset. File dữ liệu mới có thể cho counts khác.

## 9. Nạp dữ liệu thật vào Neo4j

### 9.1. Nạp riêng FPT

```powershell
python -B -m backend.src.graph.ingest --input data/normalized/FPT.json
```

CLI tự đọc `.env`, kết nối và ghi graph. Kết quả lần đầu có `created: true`. Chạy lại cùng snapshot đã hoàn tất có `created: false`, không tạo bản trùng.

Cùng Dataset ID nhưng nội dung hoặc graph_version khác sẽ báo xung đột; không được sửa dữ liệu rồi dùng lại cùng dataset_version.

### 9.2. Nạp toàn bộ normalized

Sau khi FPT chạy thành công và muốn thử đủ các mã trên local:

```powershell
python -B -m backend.src.graph.ingest --dry-run
python -B -m backend.src.graph.ingest
```

Không có `--input` nghĩa là lấy các file `*.json` trong `data/normalized`. CLI kiểm tra tất cả trước khi kết nối, nhưng mỗi dataset được ghi trong transaction riêng. Nếu một dataset lỗi, các dataset đã commit trước đó không bị rollback.

Phải kiểm tra `.env` đang trỏ local trước khi nạp đủ tám mã; tập dữ liệu này vượt quota của AuraDB Free. Local không có quota đó, nhưng vẫn bị giới hạn bởi RAM, CPU và ổ đĩa. Tám mã chưa được kiểm chứng nạp toàn bộ trên máy hiện tại; nên theo dõi tài nguyên khi thử.

Nếu không muốn kích hoạt environment, có thể gọi đúng Python trực tiếp:

```powershell
& "$HOME\.venv\Scripts\python.exe" -B -m backend.src.graph.ingest --input data/normalized/FPT.json
```

## 10. Kiểm tra dữ liệu và xem graph

Các truy vấn dưới đây chạy trong Neo4j Browser sau khi chọn `neo4j`.

### 10.1. Kiểm tra trạng thái dataset

```cypher
MATCH (d:Dataset)
RETURN d.id AS dataset_id, d.status AS status
ORDER BY dataset_id;
```

Dataset nạp thành công có status `COMPLETE`.

### 10.2. Đếm nút và quan hệ

Chạy riêng từng truy vấn:

```cypher
MATCH (n)
RETURN count(n) AS total_nodes;
```

```cypher
MATCH ()-[r]->()
RETURN count(r) AS total_relationships;
```

Database mới chỉ nạp snapshot FPT đã kiểm chứng có 36.295 nodes và 68.756 relationships.

### 10.3. Xem đường đi từ FPT tới báo cáo

```cypher
MATCH p = (:Company {symbol: 'FPT'})
          -[:HAS_DATASET]->(:Dataset)
          -[:HAS_REPORT]->(:FinancialReport)
RETURN p
LIMIT 20;
```

Chọn Graph để xem các nút. `LIMIT 20` giới hạn đường đi trả về, không giới hạn dung lượng database. Nếu dữ liệu có nhiều phiên bản, truy vấn này có thể hiển thị báo cáo của nhiều snapshot.

## 11. Các lần sử dụng tiếp theo

Nếu đã cài dependency và cấu hình `.env`, mỗi lần dùng chỉ cần mở Docker Desktop, mở PowerShell tại repo, rồi chạy:

```powershell
docker compose up -d --wait --wait-timeout 300 neo4j
& "$HOME\.venv\Scripts\python.exe" -B -m backend.src.graph.ingest --input data/normalized/FPT.json
```

Không cần cài lại thư viện hoặc nhập credentials mỗi lần. Khi người phụ trách data bàn giao normalized mới, chạy dry-run rồi ingestion cho file đó. Hiện chưa có lịch tự động nạp file mới.

## 12. Dừng, khởi động lại và giữ dữ liệu

| Việc cần làm | Lệnh PowerShell |
| --- | --- |
| Xem trạng thái | `docker compose ps` |
| Xem log gần nhất | `docker compose logs --tail 50 neo4j` |
| Dừng service, giữ container và volume | `docker compose stop neo4j` |
| Chạy lại container đã dừng | `docker compose start neo4j` |
| Tạo/chạy service theo cấu hình | `docker compose up -d neo4j` |
| Xem tài nguyên | `docker stats --no-stream` |
| Xem volume của project | `docker volume ls` |

`docker compose down` gỡ container/network nhưng giữ named volume. Không thêm `-v` và không xóa volume nếu muốn giữ database: các thao tác đó có thể xóa dữ liệu.

Volume là nơi lưu dữ liệu, không phải bản backup độc lập. Nếu Docker data disk hoặc volume mất, database cũng mất. Các file normalized giúp nạp lại những snapshot còn được giữ ở dạng JSON; chúng không tự lưu toàn bộ lịch sử các lần crawler chạy.

Code hiện giữ snapshot mới cùng snapshot cũ. Dung lượng tăng theo số phiên bản nạp; cần chính sách lưu lịch sử nếu chạy lâu dài. Container hiện giới hạn 2 GiB RAM, heap tối đa 768 MiB và page cache 256 MiB theo cấu hình Compose.

## 13. Xử lý các lỗi thường gặp

### Docker báo không phát hiện virtualization

Nếu Task Manager báo Disabled, xử lý BIOS/UEFI trước. Nếu firmware đã bật nhưng Docker vẫn lỗi, mở PowerShell Administrator và bật hai thành phần Windows:

```powershell
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```

Khởi động lại Windows, cập nhật WSL và mở Docker Desktop. Nếu vẫn lỗi, tiếp tục chẩn đoán hypervisor hoặc chính sách máy; không mặc định CPU không hỗ trợ. Tham khảo [hướng dẫn Microsoft](https://learn.microsoft.com/en-us/windows/wsl/install-manual).

### `Connection.MissingDatabaseError: No active database`

Trong Browser chạy riêng:

```text
:use neo4j
```

Sau đó chạy truy vấn thử. Nếu vẫn lỗi, ngắt kết nối rồi đăng nhập lại local với database `neo4j`. Không dùng tên database Aura hoặc `system` để truy vấn graph tài chính.

### CLI báo thiếu credentials

Kiểm tra `.env` nằm ở gốc repo và có URI/user/password. Mật khẩu trống không hợp lệ. Không chỉ điền `backend/.env`. Mở terminal mới nếu đang có biến cấu hình cũ.

### CLI báo `Neo4j operation failed`

Thông báo được cố ý rút gọn để không lộ credentials. Kiểm tra lần lượt:

```powershell
docker compose ps
docker compose logs --tail 50 neo4j
Test-NetConnection localhost -Port 7687
```

Thử đăng nhập Browser với cùng thông tin. Nếu đã đổi `.env` sau khi database được tạo, mật khẩu thật trong database có thể vẫn là mật khẩu ban đầu. Không xóa volume để chữa lỗi đăng nhập.

### Không tìm thấy module `neo4j` hoặc `dotenv`

Kích hoạt `$HOME\.venv` rồi cài lại đúng dependency:

```powershell
python -m pip install -r backend/requirements.txt
```

Hoặc gọi ingestion trực tiếp bằng `$HOME\.venv\Scripts\python.exe` như phần trên để tránh dùng nhầm Python.

### Cổng 7474 hoặc 7687 đã được sử dụng

Kiểm tra container khác hoặc Neo4j Desktop đang chạy. Dừng instance không cần dùng, hoặc điều chỉnh cổng host trong Compose rồi cập nhật URI và URL Browser tương ứng. Không xóa database để giải phóng cổng.

### Thay mật khẩu `.env` nhưng đăng nhập không được

`NEO4J_AUTH` chỉ đặt mật khẩu ban đầu khi database chưa có. Với volume đã chứa database, cần đăng nhập bằng mật khẩu hiện tại và đổi mật khẩu trong Neo4j, sau đó cập nhật `.env` để khớp.

## 14. Kiểm tra code graph

Chạy trong environment Python đã kích hoạt:

```powershell
python -B -m unittest discover -s backend/tests -p "test_graph*.py" -v
```

Các tests không thay thế kiểm tra server thật. Trên máy hiện tại đã kiểm chứng 29 tests pass, FPT ingestion thành công, nạp lặp không trùng, đọc lại payload đúng input và Browser HTTP trả 200. Rollback khi cố ý gây lỗi và ingestion đồng thời chưa được kiểm chứng trực tiếp.

Để hiểu cách chuyển dữ liệu thành graph, đọc [data_to_graph_flow.md](data_to_graph_flow.md). Contract chi tiết nằm trong [knowledge_graph_contract.md](knowledge_graph_contract.md).
