"use client";

import { useState } from "react";
import type { FormEvent } from "react";

import type { AnalyzeRequest } from "@/types/api";
import { hasErrors, validateForm, type FormErrors, type FormValues } from "@/lib/validation";

interface AnalyzeFormProps {
  isLoading: boolean;
  onSubmit: (request: AnalyzeRequest) => void;
}

const EMPTY_VALUES: FormValues = {
  githubUsername: "",
  jobDescription: "",
  jobTitle: "",
  jobCompany: "",
};

export function AnalyzeForm({ isLoading, onSubmit }: AnalyzeFormProps) {
  const [values, setValues] = useState<FormValues>(EMPTY_VALUES);
  const [errors, setErrors] = useState<FormErrors>({});

  function handleChange<K extends keyof FormValues>(field: K, value: string) {
    setValues((prev) => ({ ...prev, [field]: value }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationErrors = validateForm(values);
    setErrors(validationErrors);
    if (hasErrors(validationErrors)) {
      return;
    }
    onSubmit({
      github_username: values.githubUsername.trim(),
      job_description: values.jobDescription.trim(),
      job_title: values.jobTitle.trim() || null,
      job_company: values.jobCompany.trim() || null,
    });
  }

  return (
    <form onSubmit={handleSubmit} noValidate aria-busy={isLoading}>
      <div className="field">
        <label htmlFor="github-username">GitHub username</label>
        <input
          id="github-username"
          type="text"
          value={values.githubUsername}
          onChange={(event) => handleChange("githubUsername", event.target.value)}
          aria-invalid={errors.githubUsername ? "true" : "false"}
          aria-describedby={errors.githubUsername ? "github-username-error" : undefined}
          disabled={isLoading}
          autoComplete="off"
        />
        {errors.githubUsername && (
          <p className="field-error" id="github-username-error" role="alert">
            {errors.githubUsername}
          </p>
        )}
      </div>

      <div className="field">
        <label htmlFor="job-description">Job description</label>
        <textarea
          id="job-description"
          rows={10}
          value={values.jobDescription}
          onChange={(event) => handleChange("jobDescription", event.target.value)}
          aria-invalid={errors.jobDescription ? "true" : "false"}
          aria-describedby={errors.jobDescription ? "job-description-error" : undefined}
          disabled={isLoading}
        />
        {errors.jobDescription && (
          <p className="field-error" id="job-description-error" role="alert">
            {errors.jobDescription}
          </p>
        )}
      </div>

      <div className="field-row">
        <div className="field">
          <label htmlFor="job-title">Job title (optional)</label>
          <input
            id="job-title"
            type="text"
            value={values.jobTitle}
            onChange={(event) => handleChange("jobTitle", event.target.value)}
            aria-invalid={errors.jobTitle ? "true" : "false"}
            aria-describedby={errors.jobTitle ? "job-title-error" : undefined}
            disabled={isLoading}
          />
          {errors.jobTitle && (
            <p className="field-error" id="job-title-error" role="alert">
              {errors.jobTitle}
            </p>
          )}
        </div>

        <div className="field">
          <label htmlFor="job-company">Company (optional)</label>
          <input
            id="job-company"
            type="text"
            value={values.jobCompany}
            onChange={(event) => handleChange("jobCompany", event.target.value)}
            aria-invalid={errors.jobCompany ? "true" : "false"}
            aria-describedby={errors.jobCompany ? "job-company-error" : undefined}
            disabled={isLoading}
          />
          {errors.jobCompany && (
            <p className="field-error" id="job-company-error" role="alert">
              {errors.jobCompany}
            </p>
          )}
        </div>
      </div>

      <button type="submit" disabled={isLoading} aria-busy={isLoading}>
        {isLoading ? "Analyzing…" : "Analyze GitHub Evidence"}
      </button>
    </form>
  );
}
