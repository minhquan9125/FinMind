# Hướng dẫn làm Frontend theo nhóm

Đọc hết trước khi tạo branch đầu tiên. Dự án mẫu chạy được nằm ở `mau-luong-trang/` (chạy `npm install` rồi `npm run dev`). Xem mẫu trước, đọc hướng dẫn sau sẽ dễ hiểu hơn.

> TL = Tech Lead. A, B, C = thành viên.

---

## 1. Ý tưởng chính (đọc phần này nếu chỉ có 1 phút)

- Mỗi người làm **một trang** trong thư mục `pages/<tên-trang>/`. Không ai sửa trang của người khác.
- Các trang **cắm vào một khung chung** do TL dựng. Khung tự nhận trang mới, nên không ai phải sửa `App.jsx`.
- Trang này chuyển sang trang kia bằng **địa chỉ (URL)**, lấy từ một file chung `shared/paths.js`. Không import code của nhau.
- Dữ liệu (ví dụ `documentId`) đi từ trang này sang trang kia **qua địa chỉ**.
- Muốn sửa phần chung: nhờ TL, đừng tự sửa.

```
Upload ──(xong, có id)──▶ Tìm kiếm ──(bấm "Xem chi tiết")──▶ Phân tích
  /upload              /documents/:id/search            /documents/:id/analysis
```

---

## 2. File nào CHUNG, file nào RIÊNG

### Chung (TL giữ, thành viên không tự sửa)

| File | Chức năng | Lưu ý |
|---|---|---|
| `src/shared/paths.js` | Bảng địa chỉ các trang | Dễ vỡ nhất. Chỉ **thêm**, hạn chế đổi tên. Đổi hay xóa một địa chỉ sẽ làm vỡ link của người khác, phải báo cả nhóm. |
| `tailwind.config.js` | Bảng màu (`brand`, `muted`, `border`, `mark`...) | Sửa là cả các trang đổi theo. Sau khi sửa phải xem lại mọi trang. |
| `src/index.css` | Style nền, `.spinner`, style của `<mark>` | Như trên. |
| `src/app/AppShell.jsx` | Khung chung và thanh các bước | Không chứa tên trang cụ thể. Nếu bạn phải sửa file này để thêm trang thì bạn đang làm sai cách. |
| `src/app/router.jsx` | `Link`, `useNavigate`, `useParams`, `Routes` | Thành viên chỉ dùng, không sửa. |
| `src/app/routes.js` | Tự gom trang | Viết một lần, gần như không sửa. |
| `src/main.jsx`, `index.html`, `vite.config.js` | Điểm vào, cấu hình build | Chỉ TL sửa. |
| `package.json`, `package-lock.json` | Thư viện | **Dễ conflict nhất.** Cần thư viện thì xin TL. Không sửa tay lockfile. |

#### Thư mục `src/shared/` (nút, khung và tiện ích dùng chung)

| File | Chức năng |
|---|---|
| `shared/ui/Card.jsx` | Khung panel trắng bo góc (hiện đang lặp lại ở cả 4 panel) |
| `shared/ui/Button.jsx` | Nút chuẩn: xanh chính, nhạt phụ, disabled / đang tải |
| `shared/ui/ErrorText.jsx` | Chữ báo lỗi đỏ thống nhất |
| `shared/ui/Spinner.jsx` | Vòng quay đang tải |
| `shared/ui/Stat.jsx` | Ô thống kê (số + nhãn) |
| `shared/ui/index.js` | Gom export: `import { Card, Button } from "../../shared/ui"` |
| `shared/api/client.js` | Hàm gọi API lõi (base URL, xử lý lỗi); mỗi trang có `api.js` riêng và chỉ gọi qua file này |
| `shared/hooks/useDebounce.js` | Debounce cho ô nhập, tránh gọi API theo từng phím |
| `shared/format.js` | Format số, %, đơn vị tiền (triệu VND) |
| `shared/constants.js` | Hằng số dùng chung (top-K, giới hạn dòng, định dạng file) |
| `shared/paths.js` | Bảng địa chỉ các trang (đã nêu ở trên) |

#### Ba file hay bị hỏi: `constants.js`, `format.js`, `paths.js`

| File | Chứa gì | Ví dụ | Dùng khi |
|---|---|---|---|
| `shared/constants.js` | Giá trị cố định dùng chung | `TOP_K_OPTIONS = [3, 5, 10]`, `VOCAB_ROW_LIMIT = 300`, loại file cho phép upload | Cần một con số ở nhiều nơi, không gõ lại mỗi nơi một kiểu |
| `shared/format.js` | Hàm biến số thô thành chuỗi hiển thị | `3.440.840.854 triệu VND`, `87%`, `1.250 VND/cổ phiếu`, `2026-Q2` thành `Quý 2/2026` | Cần hiển thị số liệu giống nhau ở nhiều trang; luôn kèm đơn vị và kỳ |
| `shared/paths.js` | Địa chỉ (URL) của mọi trang | `PATHS.search(docId)` trả về `/documents/<id>/search` | Cần chuyển sang trang khác; không viết cứng chuỗi, không import code của nhau |

```js
// constants.js
export const TOP_K_OPTIONS = [3, 5, 10];
export const VOCAB_ROW_LIMIT = 300;

// format.js
export const formatMillionVnd = (v) => `${v.toLocaleString("vi-VN")} triệu VND`;
export const formatPercent = (score) => `${Math.round(score * 100)}%`;

// paths.js
export const PATHS = {
  upload: "/upload",
  search: (docId) => `/documents/${docId}/search`,
  analysis: (docId) => `/documents/${docId}/analysis`,
};
```

Lợi ích: đổi giá trị, cách hiển thị hay địa chỉ chỉ cần sửa **một chỗ**, mọi trang cập nhật theo. Dữ liệu tài chính hiển thị sai đơn vị hoặc sai kỳ là lỗi nghiêm trọng, nên mọi trang phải đi qua `format.js`.

Lưu ý khi dùng file trong `shared/`:
- **Ai cũng dùng được, chỉ TL sửa.** Cần nút khác kiểu thì xin TL thêm biến thể, đừng copy rồi tự sửa.
- **Sửa file chung là ảnh hưởng mọi trang.** Đổi màu nút hay bo góc `Card` thì mọi trang đổi theo; sửa xong phải xem lại cả các trang.
- **Chỉ thêm, không đổi tên.** Đổi tên một component chung (ví dụ `Button` thành `Btn`) làm vỡ import của mọi người.
- **Chỉ đưa lên `shared/` thứ mà từ 2 trang trở lên cùng cần.** Thứ chỉ một trang dùng (ví dụ `ResultCard` của trang Tìm kiếm) để trong thư mục trang đó.
- **Muốn đưa lên chung:** mở issue, TL thêm bằng PR riêng và nhỏ, rồi mọi người rebase.

### Riêng (mỗi người một thư mục)

| Thư mục | Chủ | File chính |
|---|---|---|
| `pages/upload/` | A | `index.js`, `UploadPage.jsx` |
| `pages/search/` | B | `index.js`, `SearchPage.jsx` |
| `pages/analysis/` | C | `index.js`, `AnalysisPage.jsx` |

Trong thư mục của mình bạn được tự do thêm file con (component, hook, `api.js`, `mock.js`).

### Không đưa lên GitHub
`node_modules/`, `dist/`, `.env.local` (cấu hình riêng từng máy; dùng `.env.example` làm mẫu). Riêng `package-lock.json` thì **phải commit**.

---

## 3. Cách làm một trang (làm theo thứ tự)

**Bước 1. Tạo thư mục** `pages/<tên>/` (ví dụ `pages/search/`).

**Bước 2. Viết `index.js`, đây là "hợp đồng" để cắm trang vào khung:**
```js
import SearchPage from "./SearchPage.jsx";
import { PATHS } from "../../shared/paths.js";

export default {
  id: "search",                                   // duy nhất, không trùng trang khác
  order: 2,                                       // thứ tự trên thanh các bước, không trùng
  label: "Tìm kiếm",                              // chữ hiện trên menu
  path: "/documents/:documentId/search",          // địa chỉ đăng ký với router
  link: (docId) => (docId ? PATHS.search(docId) : null),
  Component: SearchPage,
};
```

**Bước 3. Xin TL thêm địa chỉ trang vào `shared/paths.js`** (một dòng):
```js
search: (docId) => `/documents/${docId}/search`,
```

**Bước 4. Viết trang** `SearchPage.jsx`. Lấy dữ liệu từ địa chỉ:
```jsx
import { useParams } from "react-router-dom";
const { documentId } = useParams();
```

**Bước 5. Chạy thử**: `npm run dev`, mở thẳng `http://localhost:5173/documents/abc/search`. Bạn làm việc được ngay, không cần đi qua trang của người khác.

---

## 4. Cách chuyển sang trang khác ("bấm vào đây thì qua trang kia")

Luôn dùng `PATHS`, **không viết cứng** chuỗi `"/search"`:

```jsx
// Chuyển bằng nút / link
import { Link } from "react-router-dom";
import { PATHS } from "../../shared/paths.js";
<Link to={PATHS.analysis(documentId)}>Xem chi tiết chunk →</Link>

// Chuyển bằng code (sau khi xử lý xong)
import { useNavigate } from "react-router-dom";
const navigate = useNavigate();
navigate(PATHS.search(doc.id));
```

Quy tắc:
- Bạn chỉ viết **nút đi tiếp** trong trang của mình. Nội dung trang đích là việc của chủ trang đó.
- Không `import` file từ thư mục trang khác.
- Trang đích cần dữ liệu gì thì lấy từ **địa chỉ** (`useParams`, hoặc `?q=...`). Đừng trông chờ trang trước đã lưu sẵn.
- Trang đích chưa làm xong cũng không sao, link vẫn chuyển được tới một trang tạm.

---

## 5. Khi hai người cùng làm một trang (ví dụ Vũ và Huyền cùng làm upload)

Quyết định **trước khi code**. Không nói gì thì sẽ có conflict, hoặc tệ hơn là lỗi âm thầm.

| Tình huống | Cách làm |
|---|---|
| **Cùng một giao diện, chia việc** (phổ biến nhất) | Một người là **trưởng trang** (sở hữu `index.js` và trang ghép). Mỗi người một **component riêng**, mỗi file đúng một chủ. Xem ví dụ bên dưới. |
| **Hai giao diện khác nhau để so sánh** | Hai thư mục tách hẳn, **khác `id`, `path`, `order`** (ví dụ `pages/upload-vu/` và `pages/upload-huyen/`). Chọn xong thì xóa bản không dùng và đổi `path` bản được chọn về `/upload`. |
| **Trùng việc do hiểu nhầm** | Dừng lại. TL quyết định một người làm, người kia chuyển sang việc khác. |

Ví dụ chia việc cùng một trang:
```
pages/upload/
├── index.js              ← Vũ (trưởng trang)
├── UploadPage.jsx        ← Vũ (chỉ ghép các phần bên dưới)
├── FileUploader.jsx      ← Vũ làm
└── SymbolImporter.jsx    ← Huyền làm
```
```jsx
<FileUploader onDone={goNext} />
<SymbolImporter onDone={goNext} />
```
- Chia **theo file, không chia theo dòng**.
- Thống nhất trước "đầu vào, đầu ra" của component (ví dụ `onDone(doc)` trả về `{ id }`).
- Huyền xong thì báo Vũ thêm một dòng ghép vào `UploadPage.jsx`.

Cảnh báo: hai thư mục khác nhau nhưng cùng `id`, `path` hoặc `order` thì **Git không báo conflict**, nhưng trang này sẽ đè trang kia. Luôn kiểm tra trùng trước khi tạo trang mới.

---

## 6. Quy trình Git

- `main` được bảo vệ: chỉ merge bằng PR, cần ít nhất 1 review.
- Branch: `feat/<trang>-<việc>` hoặc `fix/<trang>-<lỗi>`, ví dụ `feat/search-result-card`.
- **Giao việc có ghi tên** trên GitHub Issue (một việc, một người nhận). Xem Issue trước khi nhận việc.
- **Nhận việc xong thì mở Draft PR sớm** để đồng đội thấy việc này đã có người làm. Báo trên nhóm: "Tôi nhận phần X, sửa các file Y".
- Mỗi ngày trước khi làm:
  ```bash
  git fetch origin
  git rebase origin/main
  ```
- Branch không sống quá 2-3 ngày.
- Mỗi PR một việc, chỉ chạm thư mục trang của mình.
- Cần sửa phần chung: mở issue gắn nhãn `shared`. TL sửa bằng PR riêng và nhỏ, merge nhanh, rồi mọi người rebase.

### Tự kiểm tra "mình đang sửa đúng chỗ chưa"
```bash
git diff --name-only origin/main
```
Mọi file in ra phải nằm trong `pages/<trang của bạn>/`. Nếu thấy `shared/`, `app/` hay `package.json` thì **dừng lại và hỏi TL**.

### Kiểm tra trùng trước khi tạo trang mới
```bash
git fetch origin
git ls-tree -r origin/main --name-only | grep "pages/"
```
Rồi xem `paths.js` xem `id` và `path` đã có chưa.

### CODEOWNERS (TL tạo `.github/CODEOWNERS`)
```
/frontend/src/shared/        @tech-lead
/frontend/src/app/           @tech-lead
/frontend/package*.json      @tech-lead
/frontend/src/pages/upload/  @member-a
/frontend/src/pages/search/  @member-b
/frontend/src/pages/analysis/ @member-c
```
(Thay bằng tài khoản GitHub thật.)

---

## 7. Tình huống thường gặp

| Tình huống | Làm gì |
|---|---|
| Cần một nút giống nút của người khác | Dùng `className="btn"` từ `style.css` chung, không copy code của họ. |
| Cần thêm thư viện (biểu đồ...) | Xin TL cài, không tự sửa `package.json`. |
| Muốn thêm trang mới | Tạo `pages/<tên>/index.js`, xin TL thêm một dòng vào `paths.js`. Không sửa `App.jsx`. |
| Muốn đổi địa chỉ một trang | Báo cả nhóm, TL sửa `paths.js`. |
| Hai người cùng cần một hàm tiện ích | Đưa lên `shared/` qua TL, đừng mỗi người viết một bản. |
| Backend chưa xong | Dùng dữ liệu giả (`mock.js` trong thư mục trang của mình). |
| Cần dữ liệu từ trang khác khi đang làm | Mở thẳng địa chỉ có sẵn id (ví dụ `/documents/abc/search`) hoặc đặt `id` thật vào `.env.local`. |

---

## 8. Quy ước code

- Component: **PascalCase**, đuôi `.jsx`. Không đặt trùng tên giữa các trang.
- Hàm gọi API đặt trong thư mục trang của mình (ví dụ `pages/search/api.js`), không gọi `fetch` trực tiếp trong component.
- Ô nhập gọi API theo từng phím thì phải **debounce**. Khi `documentId` đổi, xóa dữ liệu và lỗi cũ.
- Số liệu tài chính hiển thị phải **kèm đơn vị và kỳ** (triệu VND, VND/cổ phiếu, Quý 2/2026...). Sai đơn vị hoặc sai kỳ là lỗi nghiêm trọng.

---

## 9. Checklist trước khi mở PR

- [ ] Chỉ sửa file trong thư mục trang của mình (`git diff --name-only origin/main`).
- [ ] Không sửa `package.json`, `shared/`, `app/`.
- [ ] `id`, `path`, `order` của trang không trùng trang khác.
- [ ] Link sang trang khác dùng `PATHS`, không viết cứng.
- [ ] `npm run build` chạy thành công.
- [ ] Đã thử bằng tay: mở thẳng địa chỉ trang của mình và đi qua luồng thật.
- [ ] Đã xử lý trạng thái đang tải, lỗi và rỗng.
- [ ] Đã rebase `main` mới nhất, không còn conflict.
- [ ] Không commit `.env`, `.env.local`, `node_modules/`, `dist/`.

Chưa rõ thì hỏi TL trước khi sửa, đừng đoán.
