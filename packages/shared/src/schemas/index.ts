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

export type TargetRoleInput = z.infer<typeof TargetRoleSchema>;
export type PortfolioLinkInput = z.infer<typeof PortfolioLinkSchema>;
export type UploadDocumentInput = z.infer<typeof UploadDocumentSchema>;
