import type { LucideIcon } from "lucide-react";
import {
  Briefcase,
  Building2,
  Bus,
  CloudSun,
  Dumbbell,
  Folder,
  GraduationCap,
  Hash,
  HeartPulse,
  Home,
  Laptop,
  PersonStanding,
  Plane,
  Shirt,
  Smile,
  TreePine,
  Users,
  UtensilsCrossed,
  Wrench,
} from "lucide-react";
import type { FlashcardDeck } from "../../types/api";

/** Icono estable del tema. Un mazo propio, o un tema renombrado sin slug, usa carpeta. */
const THEME_ICONS: Record<string, LucideIcon> = {
  body: PersonStanding,
  business: Briefcase,
  city: Bus,
  clothes: Shirt,
  computing: Laptop,
  feelings: Smile,
  food: UtensilsCrossed,
  health: HeartPulse,
  home: Home,
  nature: TreePine,
  school: GraduationCap,
  sports: Dumbbell,
  tools: Wrench,
  travel: Plane,
  work: Building2,
  family: Users,
  weather: CloudSun,
  numbers: Hash,
};

export function deckIcon(deck: Pick<FlashcardDeck, "slug">): LucideIcon {
  return THEME_ICONS[deck.slug] ?? Folder;
}
