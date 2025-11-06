package com.gitstats.core;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.TimeUnit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Executor for Git commands with proper error handling and logging
 */
public class GitCommandExecutor {
    
    private static final Logger logger = LoggerFactory.getLogger(GitCommandExecutor.class);
    private static final int DEFAULT_TIMEOUT_SECONDS = 300; // 5 minutes
    
    private final File repositoryPath;
    private final Configuration config;
    
    public GitCommandExecutor(File repositoryPath) {
        this.repositoryPath = repositoryPath;
        this.config = Configuration.getInstance();
    }
    
    /**
     * Execute a git command and return output
     */
    public String execute(String... command) throws IOException, InterruptedException {
        return execute(DEFAULT_TIMEOUT_SECONDS, command);
    }
    
    /**
     * Execute a git command with timeout
     */
    public String execute(int timeoutSeconds, String... command) throws IOException, InterruptedException {
        List<String> fullCommand = new ArrayList<>();
        fullCommand.add("git");
        fullCommand.addAll(Arrays.asList(command));
        
        if (config.isDebug()) {
            logger.debug("Executing: {} in {}", String.join(" ", fullCommand), repositoryPath);
        }
        
        long startTime = System.currentTimeMillis();
        
        ProcessBuilder processBuilder = new ProcessBuilder(fullCommand);
        processBuilder.directory(repositoryPath);
        processBuilder.redirectErrorStream(true);
        
        Process process = processBuilder.start();
        
        StringBuilder output = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(process.getInputStream()))) {
            String line;
            while ((line = reader.readLine()) != null) {
                output.append(line).append("\n");
            }
        }
        
        boolean completed = process.waitFor(timeoutSeconds, TimeUnit.SECONDS);
        
        if (!completed) {
            process.destroyForcibly();
            throw new IOException("Command timed out after " + timeoutSeconds + " seconds");
        }
        
        int exitCode = process.exitValue();
        long duration = System.currentTimeMillis() - startTime;
        
        if (config.isVerbose()) {
            logger.info("Command completed in {}ms: {}", duration, String.join(" ", fullCommand));
        }
        
        if (exitCode != 0) {
            logger.error("Git command failed with exit code {}: {}", exitCode, output.toString());
            throw new IOException("Git command failed: " + output.toString());
        }
        
        return output.toString().trim();
    }
    
    /**
     * Check if directory is a valid git repository
     */
    public boolean isValidRepository() {
        try {
            execute(5, "rev-parse", "--git-dir");
            return true;
        } catch (Exception e) {
            logger.debug("Not a valid repository: {}", repositoryPath, e);
            return false;
        }
    }
    
    /**
     * Get the default branch name
     */
    public String getDefaultBranch() throws IOException, InterruptedException {
        try {
            // Try to get from symbolic-ref
            String result = execute("symbolic-ref", "refs/remotes/origin/HEAD");
            if (result != null && !result.isEmpty()) {
                return result.replace("refs/remotes/origin/", "").trim();
            }
        } catch (IOException e) {
            // Fall through to alternatives
        }
        
        try {
            // Try to get current branch
            String result = execute("rev-parse", "--abbrev-ref", "HEAD");
            if (result != null && !result.isEmpty() && !"HEAD".equals(result)) {
                return result.trim();
            }
        } catch (IOException e) {
            // Fall through
        }
        
        // Check common main branches
        String[] candidates = {"main", "master", "develop", "development"};
        String branches = execute("branch");
        
        for (String candidate : candidates) {
            if (branches.contains(candidate)) {
                return candidate;
            }
        }
        
        // Default to master
        return "master";
    }
    
    /**
     * Get Git version
     */
    public String getGitVersion() {
        try {
            return execute("--version");
        } catch (Exception e) {
            logger.error("Failed to get git version", e);
            return "unknown";
        }
    }
    
    /**
     * Get total commit count
     */
    public int getTotalCommits() throws IOException, InterruptedException {
        String output = execute("rev-list", "--all", "--count");
        try {
            return Integer.parseInt(output.trim());
        } catch (NumberFormatException e) {
            logger.error("Failed to parse commit count: {}", output, e);
            return 0;
        }
    }
    
    /**
     * Get commit log with format
     */
    public String getLog(String... additionalArgs) throws IOException, InterruptedException {
        List<String> args = new ArrayList<>();
        args.add("log");
        args.addAll(Arrays.asList(additionalArgs));
        return execute(args.toArray(new String[0]));
    }
    
    public File getRepositoryPath() {
        return repositoryPath;
    }
}
