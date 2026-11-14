import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "../../app/router.jsx";
import { Button, Card, EmptyState, ErrorState, Input, Skeleton, StatusBadge } from "../../shared/ui/index.js";
import { getProfile } from "./api.js";

const MAX_AVATAR_BYTES = 2 * 1024 * 1024;

export default function ProfilePage() {
  const [params] = useSearchParams();
  const fixture = ["empty", "error", "loading"].includes(params.get("fixture")) ? params.get("fixture") : "success";
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [avatarPreview, setAvatarPreview] = useState(null);
  const [avatarReady, setAvatarReady] = useState(false);
  const [avatarFeedback, setAvatarFeedback] = useState("");
  const [avatarError, setAvatarError] = useState(false);
  const [passwords, setPasswords] = useState({ current: "", next: "", confirm: "" });
  const [passwordFeedback, setPasswordFeedback] = useState("");
  const [passwordError, setPasswordError] = useState(false);
  const previewUrl = useRef(null);

  useEffect(() => {
    if (fixture === "loading") {
      setLoading(true);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getProfile(fixture === "error" && retryCount > 0 ? "success" : fixture)
      .then((data) => { if (!cancelled) setProfile(data); })
      .catch((caught) => { if (!cancelled) setError(caught.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [fixture, retryCount]);

  useEffect(() => () => { if (previewUrl.current) URL.revokeObjectURL(previewUrl.current); }, []);

  function chooseAvatar(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!["image/png", "image/jpeg"].includes(file.type) || file.size > MAX_AVATAR_BYTES) {
      if (previewUrl.current) URL.revokeObjectURL(previewUrl.current);
      previewUrl.current = null;
      setAvatarPreview(null);
      setAvatarFeedback("Vui lòng chọn ảnh PNG hoặc JPG không quá 2 MB.");
      setAvatarError(true);
      setAvatarReady(false);
      event.target.value = "";
      return;
    }
    if (previewUrl.current) URL.revokeObjectURL(previewUrl.current);
    previewUrl.current = URL.createObjectURL(file);
    setAvatarPreview(previewUrl.current);
    setAvatarReady(true);
    setAvatarError(false);
    setAvatarFeedback("Ảnh mới đã sẵn sàng để xem trước.");
  }

  function submitPassword(event) {
    event.preventDefault();
    if (!passwords.current || !passwords.next || !passwords.confirm) {
      setPasswordFeedback("Vui lòng nhập đầy đủ ba ô mật khẩu.");
      setPasswordError(true);
      return;
    }
    if (passwords.next !== passwords.confirm) {
      setPasswordFeedback("Mật khẩu xác nhận chưa khớp.");
      setPasswordError(true);
      return;
    }
    setPasswords({ current: "", next: "", confirm: "" });
    setPasswordError(false);
    setPasswordFeedback("Bản mẫu: biểu mẫu hợp lệ, mật khẩu chưa được thay đổi.");
  }

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-[#0F172A]">
      <header className="border-b border-[#E2E8F0] bg-white">
        <div className="mx-auto flex h-16 max-w-[1100px] items-center gap-2.5 px-5 sm:px-8">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#2563EB] text-xs font-bold text-white">FM</span>
          <strong className="text-lg">FinMind</strong>
        </div>
      </header>
      <main className="mx-auto max-w-[860px] px-5 pb-16 pt-9 sm:px-8 sm:pt-12">
        <Link className="text-sm font-semibold text-[#64748B] hover:text-[#0F172A]" to="/dashboard">← Về trang chủ</Link>
        <div className="mb-8 mt-6">
          <p className="text-xs font-semibold uppercase tracking-widest text-[#64748B]">Tài khoản</p>
          <h1 className="mt-2 text-[28px] font-bold tracking-tight sm:text-[32px]">Hồ sơ cá nhân</h1>
          <p className="mt-2 text-sm text-[#64748B]">Xem trước ảnh đại diện và biểu mẫu đổi mật khẩu.</p>
          <div className="mt-3"><StatusBadge tone="neutral">Bản mẫu · Chưa lưu vào tài khoản</StatusBadge></div>
        </div>

        {loading ? <Skeleton rows={6} /> : error ? (
          <ErrorState message={error} onRetry={() => setRetryCount((count) => count + 1)} />
        ) : !profile ? <EmptyState title="Chưa có hồ sơ" description="Fixture hồ sơ hiện đang rỗng." /> : (
          <div className="space-y-5">
            <Card title="Ảnh đại diện" description="Chọn ảnh để xem trước diện mạo mới." className="rounded-2xl">
              <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
                <div className="flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-full border-4 border-white bg-[#DBEAFE] text-2xl font-semibold text-[#1D4ED8] shadow-[0_0_0_1px_#BFDBFE]" aria-label="Ảnh đại diện xem trước">
                  {avatarPreview ? <img src={avatarPreview} alt="Ảnh đại diện mới" className="h-full w-full object-cover" /> : profile.initials}
                </div>
                <div>
                  <label htmlFor="avatar-input" className="inline-flex min-h-11 cursor-pointer items-center rounded-[10px] border border-[#CBD5E1] bg-white px-4 text-sm font-semibold hover:bg-[#F8FAFC] focus-within:ring-2 focus-within:ring-[#2563EB]">Chọn ảnh mới</label>
                  <input id="avatar-input" type="file" accept="image/png,image/jpeg" onChange={chooseAvatar} className="sr-only" aria-describedby="avatar-help avatar-feedback" />
                  <p id="avatar-help" className="mt-2 text-xs text-[#64748B]">PNG hoặc JPG, tối đa 2 MB.</p>
                  <p id="avatar-feedback" role="status" className={`mt-2 text-xs font-medium ${avatarError ? "text-red-600" : "text-blue-600"}`}>{avatarFeedback}</p>
                </div>
              </div>
              <div className="mt-7 flex justify-end border-t border-[#F1F5F9] pt-5">
                <Button disabled={!avatarReady} onClick={() => { setAvatarError(false); setAvatarFeedback("Bản mẫu: ảnh chỉ được xem trước, chưa lưu vào tài khoản."); }}>Lưu ảnh đại diện</Button>
              </div>
            </Card>

            <Card title="Đổi mật khẩu" description="Nhập mật khẩu hiện tại và mật khẩu mới." className="rounded-2xl">
              <form onSubmit={submitPassword} noValidate className="max-w-[520px]">
                <div className="grid gap-5 sm:grid-cols-2">
                  <Input label="Mật khẩu hiện tại" type="password" autoComplete="current-password" className="sm:col-span-2"
                    value={passwords.current} onChange={(event) => setPasswords((current) => ({ ...current, current: event.target.value }))} />
                  <Input label="Mật khẩu mới" type="password" autoComplete="new-password"
                    value={passwords.next} onChange={(event) => setPasswords((current) => ({ ...current, next: event.target.value }))} />
                  <Input label="Xác nhận mật khẩu mới" type="password" autoComplete="new-password"
                    value={passwords.confirm} onChange={(event) => setPasswords((current) => ({ ...current, confirm: event.target.value }))} />
                </div>
                <p role="status" aria-live="polite" className={`mt-4 text-xs font-medium ${passwordError ? "text-red-600" : "text-blue-600"}`}>{passwordFeedback}</p>
                <div className="mt-7 flex justify-end border-t border-[#F1F5F9] pt-5"><Button type="submit">Đổi mật khẩu</Button></div>
              </form>
            </Card>
          </div>
        )}
        <p className="mt-6 text-center text-xs text-[#94A3B8]">Bản mẫu giao diện · Thay đổi chưa được lưu vào tài khoản.</p>
      </main>
    </div>
  );
}
