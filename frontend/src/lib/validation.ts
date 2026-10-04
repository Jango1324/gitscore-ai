/**
 * Milestone 8B -- client-side mirror of the backend's TRANSPORT-level
 * limits (`gitscore.api.schemas`), for immediate UX feedback only.
 *
 * The backend remains authoritative: these are the same shape checks
 * `AnalyzeRequest` already enforces (non-empty, max length), never a
 * reimplementation of job-description parsing/semantic validation.
 */

export const GITHUB_USERNAME_MAX_LENGTH = 39;
export const JOB_DESCRIPTION_MAX_LENGTH = 20_000;
export const JOB_TITLE_MAX_LENGTH = 200;
export const JOB_COMPANY_MAX_LENGTH = 200;

export interface FormValues {
  githubUsername: string;
  jobDescription: string;
  jobTitle: string;
  jobCompany: string;
}

export interface FormErrors {
  githubUsername?: string;
  jobDescription?: string;
  jobTitle?: string;
  jobCompany?: string;
}

export function validateForm(values: FormValues): FormErrors {
  const errors: FormErrors = {};

  const username = values.githubUsername.trim();
  if (username.length === 0) {
    errors.githubUsername = "GitHub username is required.";
  } else if (username.length > GITHUB_USERNAME_MAX_LENGTH) {
    errors.githubUsername = `GitHub username must be ${GITHUB_USERNAME_MAX_LENGTH} characters or fewer.`;
  }

  const description = values.jobDescription.trim();
  if (description.length === 0) {
    errors.jobDescription = "Job description is required.";
  } else if (description.length > JOB_DESCRIPTION_MAX_LENGTH) {
    errors.jobDescription = `Job description must be ${JOB_DESCRIPTION_MAX_LENGTH.toLocaleString()} characters or fewer.`;
  }

  if (values.jobTitle.trim().length > JOB_TITLE_MAX_LENGTH) {
    errors.jobTitle = `Job title must be ${JOB_TITLE_MAX_LENGTH} characters or fewer.`;
  }

  if (values.jobCompany.trim().length > JOB_COMPANY_MAX_LENGTH) {
    errors.jobCompany = `Company must be ${JOB_COMPANY_MAX_LENGTH} characters or fewer.`;
  }

  return errors;
}

export function hasErrors(errors: FormErrors): boolean {
  return Object.keys(errors).length > 0;
}
