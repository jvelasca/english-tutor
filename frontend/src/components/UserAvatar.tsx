import type { User } from "../types/api";
import { avatarColor, initials } from "../utils/avatar";

interface UserAvatarProps {
  user: User;
  size?: number;
}

export function UserAvatar({ user, size = 32 }: UserAvatarProps) {
  if (user.avatar_image) {
    return (
      <img
        className="user-avatar user-avatar--image"
        src={user.avatar_image}
        alt=""
        style={{ width: size, height: size }}
        aria-hidden="true"
      />
    );
  }

  return (
    <span
      className="user-avatar"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.44,
        background: avatarColor(user),
      }}
      aria-hidden="true"
    >
      {user.avatar_emoji || initials(user.name)}
    </span>
  );
}
