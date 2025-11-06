package com.gitstats.model;

import java.time.LocalDateTime;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/**
 * Statistics for a single author/contributor
 */
public class AuthorStatistics {
    
    private final String name;
    private int totalCommits;
    private long linesAdded;
    private long linesRemoved;
    private LocalDateTime firstCommit;
    private LocalDateTime lastCommit;
    private final Set<String> activeDays;
    private final Set<String> modifiedFiles;
    private final Map<Integer, Integer> commitsByMonth;
    private final Map<Integer, Integer> commitsByYear;
    
    public AuthorStatistics(String name) {
        this.name = name;
        this.activeDays = new HashSet<>();
        this.modifiedFiles = new HashSet<>();
        this.commitsByMonth = new HashMap<>();
        this.commitsByYear = new HashMap<>();
    }
    
    public String getName() {
        return name;
    }
    
    public int getTotalCommits() {
        return totalCommits;
    }
    
    public void incrementCommits() {
        this.totalCommits++;
    }
    
    public long getLinesAdded() {
        return linesAdded;
    }
    
    public void addLinesAdded(long lines) {
        this.linesAdded += lines;
    }
    
    public long getLinesRemoved() {
        return linesRemoved;
    }
    
    public void addLinesRemoved(long lines) {
        this.linesRemoved += lines;
    }
    
    public LocalDateTime getFirstCommit() {
        return firstCommit;
    }
    
    public void setFirstCommit(LocalDateTime firstCommit) {
        if (this.firstCommit == null || firstCommit.isBefore(this.firstCommit)) {
            this.firstCommit = firstCommit;
        }
    }
    
    public LocalDateTime getLastCommit() {
        return lastCommit;
    }
    
    public void setLastCommit(LocalDateTime lastCommit) {
        if (this.lastCommit == null || lastCommit.isAfter(this.lastCommit)) {
            this.lastCommit = lastCommit;
        }
    }
    
    public Set<String> getActiveDays() {
        return Collections.unmodifiableSet(activeDays);
    }
    
    public void addActiveDay(String day) {
        activeDays.add(day);
    }
    
    public Set<String> getModifiedFiles() {
        return Collections.unmodifiableSet(modifiedFiles);
    }
    
    public void addModifiedFile(String file) {
        modifiedFiles.add(file);
    }
    
    public Map<Integer, Integer> getCommitsByMonth() {
        return Collections.unmodifiableMap(commitsByMonth);
    }
    
    public void incrementCommitsByMonth(int month) {
        commitsByMonth.merge(month, 1, Integer::sum);
    }
    
    public Map<Integer, Integer> getCommitsByYear() {
        return Collections.unmodifiableMap(commitsByYear);
    }
    
    public void incrementCommitsByYear(int year) {
        commitsByYear.merge(year, 1, Integer::sum);
    }
    
    public int getActiveDaysCount() {
        return activeDays.size();
    }
    
    public int getModifiedFilesCount() {
        return modifiedFiles.size();
    }
    
    public double getAverageCommitsPerDay() {
        if (activeDays.isEmpty()) {
            return 0.0;
        }
        return (double) totalCommits / activeDays.size();
    }
}
