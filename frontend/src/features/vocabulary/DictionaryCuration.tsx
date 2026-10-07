import { useEffect, useState } from "react";

import {
  deleteCuratedDictionary,
  saveCuratedDictionary,
  type DictionaryDirection,
} from "../../api/dictionaryAdmin";
import { getAdminPin, setAdminPin } from "../../api/audioLibrary";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { useI18n } from "../../hooks/useI18n";

/**
 * Corrección manual de una ficha del diccionario (V3.95.0, webmaster).
 *
 * La usa el webmaster desde la propia consulta: guarda el equivalente correcto
 * del término que se está viendo y esa corrección manda sobre el glosario, los
 * packs y la caché del modelo para TODOS los usuarios. El candado es el PIN de
 * administración (mismo `X-Admin-Pin` que la biblioteca de audio); el backend
 * exige además que la petición venga del propio equipo.
 *
 * Es deliberadamente pequeño: no lista las correcciones (para eso está la
 * consola), solo corrige el término en pantalla. Si el término ya estaba
 * corregido, guardar lo sobrescribe y «Quitar corrección» lo devuelve a la
 * autoridad inferior.
 */
export function DictionaryCuration({
  direction,
  word,
  translation,
  onSaved,
}: {
  direction: DictionaryDirection;
  word: string;
  translation: string | null;
  onSaved?: () => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [pin, setPin] = useState(() => getAdminPin());
  const [translationDraft, setTranslationDraft] = useState(translation ?? "");
  const [definitionDraft, setDefinitionDraft] = useState("");
  const [noteDraft, setNoteDraft] = useState("");
  const [status, setStatus] = useState<
    "idle" | "saving" | "saved" | "removed" | "error"
  >("idle");

  // Cambiar de término reinicia el formulario: la corrección es de `word`.
  useEffect(() => {
    setTranslationDraft(translation ?? "");
    setDefinitionDraft("");
    setNoteDraft("");
    setStatus("idle");
  }, [word, translation, direction]);

  async function handleSave() {
    const trimmed = pin.trim();
    if (!trimmed || !translationDraft.trim()) {
      setStatus("error");
      return;
    }
    setAdminPin(trimmed);
    setStatus("saving");
    try {
      await saveCuratedDictionary({
        direction,
        word,
        translation: translationDraft.trim(),
        definition: definitionDraft.trim(),
        note: noteDraft.trim(),
      });
      setStatus("saved");
      onSaved?.();
    } catch {
      setStatus("error");
    }
  }

  async function handleRemove() {
    setStatus("saving");
    try {
      await deleteCuratedDictionary(direction, word);
      setStatus("removed");
      onSaved?.();
    } catch {
      setStatus("error");
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-end">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-label={t("dictionary.admin.curateAria")}
          onClick={() => setOpen((value) => !value)}
        >
          {t("dictionary.admin.curateCta")}
        </Button>
      </div>
      {open && (
        <Card className="flex flex-col gap-3 border-dashed p-4 text-sm">
          <p className="font-medium">{t("dictionary.admin.curateTitle")}</p>
          <p className="text-xs text-muted-foreground">
            {t("dictionary.admin.curateHint")}
          </p>
          <p className="text-xs text-muted-foreground">
            {direction === "es-en" ? `ES → EN · ${word}` : `EN → ES · ${word}`}
          </p>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">
              {t("dictionary.admin.curateTranslation")}
            </span>
            <input
              className="rounded-md border bg-transparent px-2 py-1"
              value={translationDraft}
              onChange={(event) => setTranslationDraft(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">
              {t("dictionary.admin.curateDefinition")}
            </span>
            <input
              className="rounded-md border bg-transparent px-2 py-1"
              value={definitionDraft}
              onChange={(event) => setDefinitionDraft(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">
              {t("dictionary.admin.curateNote")}
            </span>
            <input
              className="rounded-md border bg-transparent px-2 py-1"
              value={noteDraft}
              onChange={(event) => setNoteDraft(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">
              {t("dictionary.admin.curatePin")}
            </span>
            <input
              className="rounded-md border bg-transparent px-2 py-1"
              type="password"
              value={pin}
              onChange={(event) => setPin(event.target.value)}
            />
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              size="sm"
              disabled={status === "saving"}
              onClick={() => void handleSave()}
            >
              {t("dictionary.admin.curateSave")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={status === "saving"}
              onClick={() => void handleRemove()}
            >
              {t("dictionary.admin.curateDelete")}
            </Button>
            {status === "saved" && (
              <span className="text-xs text-primary">
                {t("dictionary.admin.curateSaved")}
              </span>
            )}
            {status === "removed" && (
              <span className="text-xs text-primary">
                {t("dictionary.admin.curateRemoved")}
              </span>
            )}
            {status === "error" && (
              <span className="text-xs text-destructive">
                {t("dictionary.admin.curateError")}
              </span>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
