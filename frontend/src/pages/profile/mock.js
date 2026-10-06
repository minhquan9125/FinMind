import { researcherMock } from "../dashboard/mock.js";

// Thông tin tài khoản minh họa, chưa có backend quản lý hồ sơ.
export const profileMock = { ...researcherMock, avatarUrl: null };

export const profileFixtures = {
  success: profileMock,
  empty: null,
  error: "Không thể tải hồ sơ minh họa.",
};
