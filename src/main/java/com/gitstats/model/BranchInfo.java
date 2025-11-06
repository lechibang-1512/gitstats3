package com.gitstats.model;

import java.time.LocalDateTime;

/**
 * Information about a branch in the repository
 */
public class BranchInfo {
    
    private final String name;
    private int commitCount;
    private LocalDateTime lastCommitDate;
    private String lastCommitAuthor;
    private boolean isMerged;
    
    public BranchInfo(String name) {
        this.name = name;
    }
    
    public String getName() {
        return name;
    }
    
    public int getCommitCount() {
        return commitCount;
    }
    
    public void setCommitCount(int commitCount) {
        this.commitCount = commitCount;
    }
    
    public LocalDateTime getLastCommitDate() {
        return lastCommitDate;
    }
    
    public void setLastCommitDate(LocalDateTime lastCommitDate) {
        this.lastCommitDate = lastCommitDate;
    }
    
    public String getLastCommitAuthor() {
        return lastCommitAuthor;
    }
    
    public void setLastCommitAuthor(String lastCommitAuthor) {
        this.lastCommitAuthor = lastCommitAuthor;
    }
    
    public boolean isMerged() {
        return isMerged;
    }
    
    public void setMerged(boolean merged) {
        isMerged = merged;
    }
}
