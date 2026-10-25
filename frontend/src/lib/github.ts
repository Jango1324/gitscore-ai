/**
 * Milestone 9E -- a real, verifiable GitHub repository link, constructed
 * only from facts the API already returned (`RepositoryIdentity.owner`/
 * `.name` -- the candidate's own account/repository, already confirmed
 * to exist by the GitHub API during evidence extraction). This is NOT a
 * fabricated URL: GitHub's own `https://github.com/{owner}/{repo}` path
 * convention is a public, stable fact, not a guess.
 *
 * Deliberately links the REPOSITORY ROOT ONLY, never a file-specific
 * deep link -- `EvidenceItem.file_path` has no accompanying branch/ref,
 * and the domain model does not record one (see `evidence.models.Evidence`'s
 * own docstring for why no `source_url` field exists at all). Guessing a
 * branch name (e.g. "main") to build a `/blob/<branch>/<path>` URL could
 * produce a dead or wrong link for a repository using a different
 * default branch -- exactly the kind of fabricated-looking link this
 * milestone's "never fabricate missing URLs" instruction rules out.
 */
export function repositoryUrl(owner: string, name: string): string {
  return `https://github.com/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`;
}
