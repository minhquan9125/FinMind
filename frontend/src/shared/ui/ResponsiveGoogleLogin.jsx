import { useEffect, useRef, useState } from "react";
import { GoogleLogin } from "@react-oauth/google";

export default function ResponsiveGoogleLogin(props) {
  const host = useRef(null);
  const [width, setWidth] = useState(280);
  useEffect(() => {
    const element = host.current;
    const update = () =>
      setWidth(Math.max(200, Math.min(380, Math.floor(element.clientWidth))));
    const observer = new ResizeObserver(update);
    observer.observe(element);
    update();
    return () => observer.disconnect();
  }, []);
  return (
    <div ref={host} style={{ width: "100%", minWidth: 0 }}>
      <GoogleLogin {...props} width={width} />
    </div>
  );
}
