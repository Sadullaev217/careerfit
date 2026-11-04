// Core domain types shared between web, mobile, and API

export type SkillLevel = 'beginner' | 'intermediate' | 'advanced' | 'expert';

export type DocumentType = 'resume' | 'cover_letter' | 'portfolio_link';

export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed';

export type SubscriptionPlan = 'free' | 'pro';

export interface Profile {
  id: string;
  userId: string;
  displayName: string | null;
  avatarUrl: string | null;
  plan: SubscriptionPlan;
  analysesThisMonth: number;
  createdAt: string;
  updatedAt: string;
}

export interface Document {
  id: string;
  userId: string;
  type: DocumentType;
  fileName: string | null;
  fileUrl: string | null;
  parsedText: string | null;
  status: 'pending' | 'parsing' | 'ready' | 'failed';
  createdAt: string;
}

export interface Skill {
  id: string;
  name: string;
  escoId: string | null;
  category: string | null;
}

export interface ProfileSkill {
  skillId: string;
  skill: Skill;
  level: SkillLevel;
  yearsOfExperience: number;
}

export interface TargetRole {
  id: string;
  userId: string;
  title: string;
  region: string;
  industry: string | null;
}

export interface ScoreBreakdown {
  requiredSkills: { score: number; reason: string };
  preferredSkills: { score: number; reason: string };
  experience: { score: number; reason: string };
  education: { score: number; reason: string };
  portfolio: { score: number; reason: string };
  seniority: { score: number; reason: string };
}

export interface SalaryRange {
  min: number;
  max: number;
  median: number;
  currency: string;
  period: 'yearly' | 'monthly';
}

export interface RecommendedAction {
  type: 'course' | 'project' | 'resume_rewrite';
  skill: string;
  description: string;
  effortWeeks: number;
  priority: 'high' | 'medium' | 'low';
  beforeExample?: string;
  afterExample?: string;
}

export interface AlternativeRole {
  title: string;
  matchScore: number;
  reason: string;
  salaryRange: SalaryRange;
}

export interface ImprovementPlan {
  thirtyDays: string[];
  sixtyDays: string[];
  ninetyDays: string[];
}

export interface AnalysisResult {
  overallScore: number;
  confidence: number;
  scoreBreakdown: ScoreBreakdown;
  salaryRange: SalaryRange;
  missingSkills: Array<{ skill: string; impact: number; requiredByPercent: number }>;
  recommendedActions: RecommendedAction[];
  alternativeRoles: AlternativeRole[];
  improvementPlan: ImprovementPlan;
  disclaimer: string;
}

export interface Analysis {
  id: string;
  userId: string;
  targetRoleId: string;
  status: AnalysisStatus;
  result: AnalysisResult | null;
  createdAt: string;
  completedAt: string | null;
}

export interface HealthResponse {
  status: 'ok';
  version: string;
  timestamp: string;
}
