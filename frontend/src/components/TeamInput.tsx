import { useEffect, useId, useState } from "react";
import { api } from "../api";

/** Team-Eingabe mit Autovervollständigung aus bereits vergebenen Teamnamen. */
export function TeamInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const listId = useId();
  const [teams, setTeams] = useState<string[]>([]);

  useEffect(() => {
    api.listTeams().then(setTeams).catch(() => {});
  }, []);

  return (
    <>
      <input
        list={listId}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
      <datalist id={listId}>
        {teams.map((t) => (
          <option key={t} value={t} />
        ))}
      </datalist>
    </>
  );
}
