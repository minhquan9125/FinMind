import { useEffect, useRef, useState } from "react";
import { useNavigate } from "../../app/router.jsx";
import CompanyPreviewHero from "./CompanyPreviewHero.jsx";
import AppIcon from "../../shared/ui/AppIcon.jsx";
import { Layers3, FileCheck2, MessagesSquare } from "lucide-react";
import FinMindMark from "../../shared/ui/FinMindMark.jsx";
import LandingPointerGlow from "./LandingPointerGlow.jsx";
import "./landingRefinement.css";

/** Approved review layout, implemented as React; internal links keep router guards. */
export default function HomePage() {
  const navigate = useNavigate();
  const host = useRef(null);
  const [motionPaused, setMotionPaused] = useState(false);
  useEffect(() => {
    const elements = host.current.querySelectorAll(".reveal, .hero-enter");
    const observer = new IntersectionObserver(
      (entries) =>
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible", "is-visible");
            observer.unobserve(entry.target);
          }
        }),
      { threshold: 0.08 },
    );
    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, []);
  const followLink = (event) => {
    const link = event.target.closest("a");
    if (
      !link ||
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey ||
      link.target ||
      link.hasAttribute("download")
    )
      return;
    const href = link.getAttribute("href");
    if (
      href?.startsWith("/") &&
      !href.startsWith("//") &&
      !href.startsWith("/models/")
    ) {
      event.preventDefault();
      navigate(href);
      window.scrollTo(0, 0);
    }
  };
  return (
    <div className="fm-approved-landing" ref={host} onClick={followLink}>
      <div
        className={`landing landing-v4 ${motionPaused ? "motion-off" : ""}`}
        id="landing-page"
      >
        <LandingPointerGlow paused={motionPaused} />
        <header className="v4-nav">
          <div className="v4-width v4-nav-inner">
            <a className="landing-brand" href="/">
              <FinMindMark />
              <span>{"FinMind"}</span>
            </a>
            <nav aria-label="Điều hướng trang giới thiệu">
              <a href="#workspace-feature">{"Workspace"}</a>
              <a href="#copilot-feature">{"Trợ lý AI"}</a>
              <a href="/companies">{"Doanh nghiệp"}</a>
            </nav>
            <div className="v4-nav-actions">
              <a href="/login">{"Đăng nhập"}</a>
              <a className="btn btn-primary" href="/register">
                {"Bắt đầu nghiên cứu"}
                <AppIcon name="arrow" className="icon" />
              </a>
            </div>
          </div>
          <div className="landing-read-progress" aria-hidden="true"></div>
        </header>
        <section className="v4-hero">
          <div className="v4-hero-glow"></div>
          <div className="v4-width">
            <div className="v4-hero-copy">
              <div className="v4-release hero-enter">
                <span>{"FINMIND"}</span>
                {"Nghiên cứu doanh nghiệp Việt Nam, có ngữ cảnh "}
                <AppIcon name="arrow" className="icon" />
              </div>
              <h1 className="hero-enter delay-1">
                {"Thị trường rõ nét."}
                <br />
                <span>{"Doanh nghiệp rõ nguồn."}</span>
              </h1>
              <p className="hero-enter delay-2">
                {
                  "Từ dữ liệu thị trường, tin doanh nghiệp đến báo cáo và bằng chứng."
                }
                <br />
                {"Một không gian để bạn tự xây dựng góc nhìn nghiên cứu."}
              </p>
              <div className="v4-hero-actions hero-enter delay-3">
                <a className="btn btn-primary" href="/dashboard">
                  {"Khám phá thị trường"}
                  <AppIcon name="arrow" className="icon" />
                </a>
                <a className="btn btn-plain" href="/research">
                  {"Hỏi FinMind"}
                  <AppIcon name="copilot" className="icon" />
                </a>
              </div>
              <p className="v4-sample-note">
                {"Dữ liệu thị trường · Báo cáo doanh nghiệp · Trích dẫn nguồn"}
              </p>
            </div>
            <section className="v4-research-product" id="research">
              <CompanyPreviewHero />
            </section>
          </div>
        </section>
        <section
          className="v4-width v4-section v4-ecosystem"
          id="workspace-feature"
        >
          <div className="v4-split">
            <div className="v4-section-copy reveal">
              <p className="v4-kicker">
                <Layers3 aria-hidden="true" />
                {"Một không gian, nhiều góc nhìn"}
              </p>
              <h2>
                {"Thấy toàn cảnh."}
                <br />
                {"Hiểu từng doanh nghiệp."}
              </h2>
              <p>
                {
                  "Đi từ chỉ số đến mã cổ phiếu, từ một bài tin đến báo cáo tài chính. Các phần thông tin được đặt cạnh nhau để bạn giữ được ngữ cảnh."
                }
              </p>
              <ul className="v4-feature-list">
                <li>
                  <AppIcon name="check" className="icon" />
                  {"Theo dõi thị trường và các mã quan tâm"}
                </li>
                <li>
                  <AppIcon name="check" className="icon" />
                  {"Đọc chỉ tiêu theo kỳ, đơn vị và trạng thái"}
                </li>
                <li>
                  <AppIcon name="check" className="icon" />
                  {"Kết nối câu hỏi với bằng chứng hiện có"}
                </li>
              </ul>
              <a className="btn btn-primary" href="/dashboard">
                {"Khám phá workspace"}
                <AppIcon name="arrow" className="icon" />
              </a>
            </div>
            <div className="v4-orbit reveal">
              <div className="orbit-path orbit-one"></div>
              <div className="orbit-path orbit-two"></div>
              <div className="orbit-core">
                <FinMindMark />
                <strong>{"FinMind"}</strong>
                <span>{"RESEARCH WORKSPACE"}</span>
              </div>
              <div className="orbit-node orbit-top orbit-blue">
                <AppIcon name="compare" className="icon" />
                <span>{"Thị trường"}</span>
              </div>
              <div className="orbit-node orbit-right-top orbit-gold">
                <AppIcon name="document" className="icon" />
                <span>{"Báo cáo"}</span>
              </div>
              <div className="orbit-node orbit-right-bottom orbit-violet">
                <AppIcon name="copilot" className="icon" />
                <span>{"Copilot"}</span>
              </div>
              <div className="orbit-node orbit-bottom orbit-mint">
                <AppIcon name="graph" className="icon" />
                <span>{"Đồ thị tri thức"}</span>
              </div>
              <div className="orbit-node orbit-left-bottom orbit-peach">
                <AppIcon name="copilot" className="icon" />
                <span>{"Tin doanh nghiệp"}</span>
              </div>
              <div className="orbit-node orbit-left-top orbit-blue">
                <AppIcon name="watchlist" className="icon" />
                <span>{"Theo dõi"}</span>
              </div>
            </div>
          </div>
        </section>
        <section className="v4-evidence-section">
          <div className="v4-width v4-section v4-split reverse">
            <div className="v4-evidence-demo reveal">
              <div className="evidence-demo-header">
                <span className="evidence-demo-icon">
                  <AppIcon name="document" className="icon" />
                </span>
                <div>
                  <strong>{"Đọc báo cáo cùng bằng chứng"}</strong>
                  <small>{"Doanh nghiệp · Kỳ báo cáo · Nguồn gốc"}</small>
                </div>
                <span className="status">{"Quy trình nghiên cứu"}</span>
              </div>
              <div className="evidence-demo-metrics">
                <div>
                  <span>{"Bắt đầu từ doanh nghiệp"}</span>
                  <strong>
                    {"Chọn mã "}
                    <small>{"cổ phiếu"}</small>
                  </strong>
                  <p>{"Mở dữ liệu được lưu trong hệ thống"}</p>
                </div>
                <div className="evidence-demo-period">
                  <span>{"Kỳ báo cáo"}</span>
                  <strong>{"Chọn kỳ"}</strong>
                  <small>{"Đọc cùng phạm vi & đơn vị"}</small>
                </div>
              </div>
              <blockquote>
                <span>{"ĐỐI CHIẾU TÀI LIỆU GỐC"}</span>
                {
                  "Đối chiếu chỉ tiêu với đúng doanh nghiệp, kỳ báo cáo và đoạn nguồn hỗ trợ."
                }
              </blockquote>
              <div className="evidence-demo-footer">
                <AppIcon name="shield" className="icon" />
                {
                  "Có trích dẫn không đồng nghĩa toàn bộ diễn giải đã được xác minh."
                }
              </div>
            </div>
            <div className="v4-section-copy reveal">
              <p className="v4-kicker gold">
                <FileCheck2 aria-hidden="true" />
                {"Đọc dữ liệu cùng bằng chứng"}
              </p>
              <h2>
                {"Mỗi con số,"}
                <br />
                {"đều cần bối cảnh."}
              </h2>
              <p>
                {
                  "Ngày công bố, đơn vị và phạm vi báo cáo tạo nên ý nghĩa của một chỉ tiêu. FinMind đặt các thông tin đó trong cùng luồng đọc, để bạn có thể mở và tự đối chiếu."
                }
              </p>
              <div className="v4-context-tags">
                <span>{"Kỳ báo cáo"}</span>
                <span>{"Đơn vị"}</span>
                <span>{"Trạng thái"}</span>
                <span>{"Đoạn nguồn"}</span>
              </div>
              <a className="v4-text-link" href="/companies/FPT?tab=finance">
                {"Xem dữ liệu doanh nghiệp "}
                <AppIcon name="arrow" className="icon" />
              </a>
            </div>
          </div>
        </section>
        <section className="v4-width v4-dark-wrapper" id="copilot-feature">
          <div className="v4-dark-feature">
            <div className="v4-dark-glow"></div>
            <div className="v4-dark-head reveal">
              <p className="v4-kicker violet">
                <MessagesSquare aria-hidden="true" />
                {"FinMind Research Copilot"}
              </p>
              <h2>
                {"Một câu hỏi tốt."}
                <br />
                <span>{"Nhiều điều đáng khám phá."}</span>
              </h2>
              <p>
                {
                  "Giữ doanh nghiệp, kỳ báo cáo và nguồn trong cùng cuộc hội thoại."
                }
              </p>
            </div>
            <div className="v4-dark-split">
              <div className="v4-dark-copy reveal">
                <div className="v4-capability">
                  <span>{"01"}</span>
                  <div>
                    <h3>{"Hỏi có phạm vi."}</h3>
                    <p>{"Bắt đầu từ mã, kỳ và chỉ tiêu bạn cần tìm."}</p>
                  </div>
                </div>
                <div className="v4-capability">
                  <span>{"02"}</span>
                  <div>
                    <h3>{"Đọc có bằng chứng."}</h3>
                    <p>
                      {"Mở trích dẫn và kiểm tra đoạn nguồn đi cùng phản hồi."}
                    </p>
                  </div>
                </div>
                <div className="v4-capability">
                  <span>{"03"}</span>
                  <div>
                    <h3>{"Biết cả giới hạn."}</h3>
                    <p>
                      {"Dữ liệu thiếu hoặc đơn vị chưa chuẩn hóa được ghi rõ."}
                    </p>
                  </div>
                </div>
                <a className="btn btn-primary" href="/research">
                  {"Thử một câu hỏi"}
                  <AppIcon name="arrow" className="icon" />
                </a>
              </div>
              <div className="v4-chat-demo reveal">
                <div className="v4-chat-header">
                  <AppIcon name="copilot" className="icon" />
                  <strong>{"FinMind Copilot"}</strong>
                  <span>{"Nghiên cứu có nguồn"}</span>
                </div>
                <div className="v4-chat-user">
                  {"Bắt đầu nghiên cứu một doanh nghiệp"}
                </div>
                <div className="v4-chat-answer">
                  <span>{"TỪ CÂU HỎI ĐẾN BẰNG CHỨNG"}</span>
                  <p>
                    {"Chọn doanh nghiệp, kỳ báo cáo và chỉ tiêu. "}
                    <strong>{"Kiểm tra nguồn trong từng phản hồi."}</strong>
                  </p>
                  <p>
                    {
                      "Mở Trợ lý nghiên cứu để gửi câu hỏi và nhận kết quả từ dữ liệu hệ thống."
                    }
                  </p>
                  <a className="v4-chat-source" href="/research">
                    <AppIcon name="document" className="icon" />
                    {"Đọc nguồn & bằng chứng "}
                    <AppIcon name="external" className="icon" />
                  </a>
                </div>
                <div className="v4-chat-composer">
                  {"Câu hỏi tiếp theo của bạn…"}
                  <span>
                    <AppIcon name="arrow" className="icon" />
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>
        <section className="v4-width v4-final-cta reveal">
          <h2>
            {"Góc nhìn của bạn."}
            <br />
            <span>{"Bắt đầu từ một câu hỏi."}</span>
          </h2>
          <p>
            {
              "Mở workspace để khám phá dữ liệu, tin và nguồn theo doanh nghiệp."
            }
          </p>
          <div className="v4-hero-actions">
            <a className="btn btn-primary" href="/register">
              {"Tạo không gian nghiên cứu"}
              <AppIcon name="arrow" className="icon" />
            </a>
            <a className="btn btn-plain" href="/login">
              {"Đăng nhập"}
            </a>
          </div>
        </section>
        <footer className="v4-footer">
          <div className="v4-width">
            <div className="v4-footer-top">
              <div className="v4-footer-brand">
                <a className="landing-brand" href="/">
                  <FinMindMark />
                  <span>{"FinMind"}</span>
                </a>
                <p>
                  {"Dữ liệu, câu hỏi và bằng chứng"}
                  <br />
                  {"cho nghiên cứu doanh nghiệp Việt Nam."}
                </p>
                <span>{"NGHIÊN CỨU CÓ NGUỒN"}</span>
              </div>
              <div>
                <h3>{"Workspace"}</h3>
                <a href="/dashboard">{"Tổng quan thị trường"}</a>
                <a href="/companies">{"Doanh nghiệp"}</a>
                <a href="/watchlist">{"Danh sách theo dõi"}</a>
              </div>
              <div>
                <h3>{"Nghiên cứu"}</h3>
                <a href="/research">{"FinMind Copilot"}</a>
                <a href="/graph">{"Đồ thị tri thức"}</a>
                <a href="/companies/FPT?tab=reports">{"Báo cáo & nguồn"}</a>
              </div>
              <div>
                <h3>{"Tin tức"}</h3>
                <a href="/dashboard#market-news">{"Tin thị trường"}</a>
                <a href="/companies/FPT?tab=news">{"Tin doanh nghiệp"}</a>
                <a href="/login">{"Đăng nhập"}</a>
              </div>
            </div>
            <div className="v4-footer-bottom">
              <span>
                {
                  "FinMind · Chỉ hỗ trợ nghiên cứu, không phải khuyến nghị đầu tư."
                }
              </span>
              <button
                className="motion-button"
                onClick={() => setMotionPaused((value) => !value)}
                aria-pressed={motionPaused}
              >
                <AppIcon name="settings" className="icon" />
                {motionPaused ? "Bật hiệu ứng" : "Tạm dừng hiệu ứng"}
              </button>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
