export const USERNAME_MIN = 3;
export const USERNAME_MAX = 20;
export const USERNAME_PATTERN = /^[a-z][a-z0-9_]+$/;

export const EMAIL_MAX = 254;
export const PASSWORD_MIN = 12;
/** bcrypt only hashes the first 72 bytes; longer secrets would silently truncate. */
export const PASSWORD_MAX_BYTES = 72;

export const UNIT_ID_PATTERN = /^[A-Za-z0-9._-]{1,64}$/;

export const GENERIC_LOGIN_ERROR = "Email or password is incorrect.";

const RESERVED_USERNAMES = new Set([
  "admin",
  "administrator",
  "root",
  "system",
  "support",
  "help",
  "api",
  "www",
  "mail",
  "ftp",
  "null",
  "undefined",
  "anonymous",
  "user",
  "users",
  "profile",
  "account",
  "accounts",
  "login",
  "signup",
  "signin",
  "signout",
  "logout",
  "auth",
  "oauth",
  "official",
  "tpwd",
  "texas",
  "moderator",
  "mod",
  "staff",
  "owner",
  "security",
  "contact",
  "info",
  "webmaster",
  "postmaster",
  "me",
  "you",
  "here",
  "test",
  "guest",
  "superuser",
  "sysadmin",
  "administrator1",
  "about",
  "settings",
  "config",
]);

/** Common passwords plus short classics. Compared after lowercasing. */
const COMMON_PASSWORDS = new Set([
  "password",
  "password1",
  "password12",
  "password123",
  "password1234",
  "password12345",
  "passw0rd",
  "passw0rd123",
  "passw0rd1234",
  "123456",
  "123456789",
  "1234567890",
  "123456789012",
  "1234567890123",
  "qwerty",
  "qwertyuiop",
  "qwertyuiopas",
  "qwerty123456",
  "letmein",
  "letmein12345",
  "welcome",
  "welcome123",
  "welcome1234",
  "welcome12345",
  "admin",
  "admin123",
  "adminadmin",
  "adminadmin12",
  "iloveyou",
  "iloveyou123",
  "iloveyou1234",
  "monkey",
  "monkey123456",
  "dragon",
  "dragon123456",
  "master",
  "master123456",
  "sunshine",
  "sunshine1234",
  "princess",
  "princess1234",
  "football",
  "football1234",
  "baseball",
  "baseball1234",
  "abc123",
  "abcdefghijkl",
  "abcdef123456",
  "changeme",
  "changeme1234",
  "hunter2",
  "hunter2hunter",
  "trustno1",
  "trustno11234",
  "login",
  "login1234567",
  "starwars",
  "starwars1234",
  "whatever",
  "whatever1234",
  "password!",
  "password!!",
  "p@ssw0rd",
  "p@ssword1234",
  "111111111111",
  "000000000000",
  "aaaaaaaaaaaa",
  "texashunting",
  "texashunt123",
  "texas1234567",
  "hunting12345",
  "letmeinplease",
]);

const EMAIL_PATTERN =
  /^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$/;

export function utf8ByteLength(value: string): number {
  return new TextEncoder().encode(value).length;
}

export function normalizeUsername(raw: string): string {
  return raw.trim().toLowerCase();
}

export function normalizeEmail(raw: string): string {
  return raw.trim().toLowerCase();
}

export function isGeneratedUsername(username: string): boolean {
  return /^user_[a-f0-9]{8,16}$/.test(username);
}

export function isValidUnitId(unitId: string): boolean {
  return UNIT_ID_PATTERN.test(unitId);
}

export function validateUsername(raw: string): string | null {
  const username = normalizeUsername(raw);
  if (username.length < USERNAME_MIN || username.length > USERNAME_MAX) {
    return `Username must be ${USERNAME_MIN}–${USERNAME_MAX} characters.`;
  }
  if (!USERNAME_PATTERN.test(username)) {
    return "Username must start with a letter and use only lowercase letters, numbers, and underscores.";
  }
  if (RESERVED_USERNAMES.has(username)) {
    return "That username is reserved. Choose another.";
  }
  return null;
}

export function validateEmail(raw: string): string | null {
  const email = normalizeEmail(raw);
  if (!email) return "Enter an email address.";
  if (email.length > EMAIL_MAX) return "Email is too long.";
  const at = email.indexOf("@");
  if (at < 1 || at > 64) return "Enter a valid email address.";
  if (!EMAIL_PATTERN.test(email)) return "Enter a valid email address.";
  return null;
}

export function validatePassword(password: string, email: string, username: string): string | null {
  if (password.length < PASSWORD_MIN) {
    return `Password must be at least ${PASSWORD_MIN} characters.`;
  }
  if (utf8ByteLength(password) > PASSWORD_MAX_BYTES) {
    return `Password must be at most ${PASSWORD_MAX_BYTES} bytes (bcrypt limit).`;
  }
  const lower = password.toLowerCase();
  if (COMMON_PASSWORDS.has(lower)) {
    return "Choose a less common password.";
  }
  const emailNorm = normalizeEmail(email);
  const userNorm = normalizeUsername(username);
  if (emailNorm && lower === emailNorm) {
    return "Password cannot be the same as your email.";
  }
  const local = emailNorm.split("@")[0] ?? "";
  if (local.length >= 3 && lower === local) {
    return "Password cannot be the same as your email.";
  }
  if (userNorm.length >= 3 && lower === userNorm) {
    return "Password cannot be the same as your username.";
  }
  return null;
}

export function validateSignUp(input: { email: string; password: string; username: string }): string | null {
  return (
    validateUsername(input.username) ||
    validateEmail(input.email) ||
    validatePassword(input.password, input.email, input.username)
  );
}
