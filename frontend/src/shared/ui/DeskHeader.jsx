import AppIcon from './AppIcon.jsx';
export default function DeskHeader({ title, section = 'Không gian nghiên cứu', description, children }) {
  return <header className="desk-pagebar">
    <div className="desk-breadcrumb"><AppIcon name="document" /><span>FinMind</span><span>/</span><span>{section}</span></div>
    <div className="desk-pagebar-row"><div><h1>{title}</h1>{description && <p>{description}</p>}</div><div className="desk-page-actions">{children}</div></div>
  </header>;
}
