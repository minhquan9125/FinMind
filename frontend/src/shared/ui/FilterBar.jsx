import Button from "./Button.jsx";
import Input from "./Input.jsx";
import Select from "./Select.jsx";

// Each filter has key, label and type: "text" or "select".
export default function FilterBar({ filters = [], values = {}, onChange, onReset }) {
  return (
    <div className="flex flex-wrap items-end gap-3 rounded-xl border border-[#E2E8F0] bg-white p-4">
      {filters.map((filter) => filter.type === "select" ? (
        <Select key={filter.key} label={filter.label} options={filter.options} value={values[filter.key] ?? ""}
          onChange={(event) => onChange(filter.key, event.target.value)} className="min-w-36 flex-1" />
      ) : (
        <Input key={filter.key} label={filter.label} placeholder={filter.placeholder} value={values[filter.key] ?? ""}
          onChange={(event) => onChange(filter.key, event.target.value)} className="min-w-48 flex-1" />
      ))}
      {onReset && <Button variant="secondary" onClick={onReset}>Đặt lại</Button>}
    </div>
  );
}
