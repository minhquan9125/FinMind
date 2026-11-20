export default function ErrorText({ children, id }) {
  if (!children) return null;
  return <p id={id} role="alert" className="mt-1 text-xs text-[#DC2626]">{children}</p>;
}
