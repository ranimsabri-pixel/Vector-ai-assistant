export const TEST_USER = {
  email: `e2e-${Date.now()}@example.com`,
  password: "TestE2E123!",
};

export const TEST_USER_2 = {
  email: `e2e-2-${Date.now()}@example.com`,
  password: "TestE2E123!",
};

/** Genere un email unique pour un test donne (evite les collisions entre tests). */
export function uniqueEmail(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 10000)}@example.com`;
}
