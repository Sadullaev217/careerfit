import { z } from 'zod';

export const TargetRoleSchema = z.object({
  title: z.string().min(1).max(200),
  region: z.string().min(1).max(100),
  industry: z.string().max(100).optional(),
});

export const PortfolioLinkSchema = z.object({
  url: z.string().url().max(2048),
});

export const UploadDocumentSchema = z.object({
  type: z.enum(['resume', 'cover_letter']),
});

// New passwords only. An older account may have a shorter one, so logging in doesn't check this.
export const MIN_PASSWORD_LENGTH = 8;
// Supabase hashes passwords with bcrypt, which ignores anything past 72 bytes.
export const MAX_PASSWORD_LENGTH = 72;

export const EmailSchema = z.string().trim().email().max(320);

export const NewPasswordSchema = z.string().min(MIN_PASSWORD_LENGTH).max(MAX_PASSWORD_LENGTH);

export type TargetRoleInput = z.infer<typeof TargetRoleSchema>;
export type PortfolioLinkInput = z.infer<typeof PortfolioLinkSchema>;
export type UploadDocumentInput = z.infer<typeof UploadDocumentSchema>;
