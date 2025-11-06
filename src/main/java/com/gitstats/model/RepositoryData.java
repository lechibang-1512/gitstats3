package com.gitstats.model;

import java.time.LocalDateTime;
import java.util.Collections;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Main data container for repository statistics
 * Thread-safe for concurrent access during analysis
 */
public class RepositoryData {
    
    private final String projectName;
    private final String repositoryPath;
    private final LocalDateTime analysisTimestamp;
    
    // Basic statistics
    private int totalCommits;
    private int totalFiles;
    private long totalLines;
    private long totalLinesAdded;
    private long totalLinesRemoved;
    private long totalSourceLines;
    private long totalCommentLines;
    private long totalBlankLines;
    
    // Time-based data
    private LocalDateTime firstCommitDate;
    private LocalDateTime lastCommitDate;
    private final Set<String> activeDays;
    
    // Author statistics
    private final Map<String, AuthorStatistics> authorStats;
    
    // Activity patterns
    private final Map<Integer, Integer> commitsByHourOfDay;
    private final Map<Integer, Integer> commitsByDayOfWeek;
    private final Map<String, Integer> commitsByMonth;
    private final Map<Integer, Integer> commitsByYear;
    
    // File statistics
    private final Map<String, Integer> fileTypes;
    private final Map<String, FileStatistics> fileStats;
    
    // Branch information
    private final Map<String, BranchInfo> branches;
    private String mainBranch;
    
    // Code metrics
    private final Map<String, CodeMetrics> fileMetrics;
    private ProjectHealthMetrics healthMetrics;
    
    public RepositoryData(String projectName, String repositoryPath) {
        this.projectName = projectName;
        this.repositoryPath = repositoryPath;
        this.analysisTimestamp = LocalDateTime.now();
        
        this.activeDays = ConcurrentHashMap.newKeySet();
        this.authorStats = new ConcurrentHashMap<>();
        this.commitsByHourOfDay = new ConcurrentHashMap<>();
        this.commitsByDayOfWeek = new ConcurrentHashMap<>();
        this.commitsByMonth = new ConcurrentHashMap<>();
        this.commitsByYear = new ConcurrentHashMap<>();
        this.fileTypes = new ConcurrentHashMap<>();
        this.fileStats = new ConcurrentHashMap<>();
        this.branches = new ConcurrentHashMap<>();
        this.fileMetrics = new ConcurrentHashMap<>();
    }
    
    // Getters and Setters
    public String getProjectName() {
        return projectName;
    }
    
    public String getRepositoryPath() {
        return repositoryPath;
    }
    
    public LocalDateTime getAnalysisTimestamp() {
        return analysisTimestamp;
    }
    
    public int getTotalCommits() {
        return totalCommits;
    }
    
    public void setTotalCommits(int totalCommits) {
        this.totalCommits = totalCommits;
    }
    
    public void incrementTotalCommits() {
        this.totalCommits++;
    }
    
    public int getTotalFiles() {
        return totalFiles;
    }
    
    public void setTotalFiles(int totalFiles) {
        this.totalFiles = totalFiles;
    }
    
    public long getTotalLines() {
        return totalLines;
    }
    
    public void setTotalLines(long totalLines) {
        this.totalLines = totalLines;
    }
    
    public long getTotalLinesAdded() {
        return totalLinesAdded;
    }
    
    public void addLinesAdded(long lines) {
        this.totalLinesAdded += lines;
    }
    
    public long getTotalLinesRemoved() {
        return totalLinesRemoved;
    }
    
    public void addLinesRemoved(long lines) {
        this.totalLinesRemoved += lines;
    }
    
    public long getTotalSourceLines() {
        return totalSourceLines;
    }
    
    public void setTotalSourceLines(long totalSourceLines) {
        this.totalSourceLines = totalSourceLines;
    }
    
    public long getTotalCommentLines() {
        return totalCommentLines;
    }
    
    public void setTotalCommentLines(long totalCommentLines) {
        this.totalCommentLines = totalCommentLines;
    }
    
    public long getTotalBlankLines() {
        return totalBlankLines;
    }
    
    public void setTotalBlankLines(long totalBlankLines) {
        this.totalBlankLines = totalBlankLines;
    }
    
    public LocalDateTime getFirstCommitDate() {
        return firstCommitDate;
    }
    
    public void setFirstCommitDate(LocalDateTime firstCommitDate) {
        this.firstCommitDate = firstCommitDate;
    }
    
    public LocalDateTime getLastCommitDate() {
        return lastCommitDate;
    }
    
    public void setLastCommitDate(LocalDateTime lastCommitDate) {
        this.lastCommitDate = lastCommitDate;
    }
    
    public Set<String> getActiveDays() {
        return Collections.unmodifiableSet(activeDays);
    }
    
    public void addActiveDay(String day) {
        activeDays.add(day);
    }
    
    public Map<String, AuthorStatistics> getAuthorStats() {
        return Collections.unmodifiableMap(authorStats);
    }
    
    public AuthorStatistics getOrCreateAuthorStats(String author) {
        return authorStats.computeIfAbsent(author, AuthorStatistics::new);
    }
    
    public Map<Integer, Integer> getCommitsByHourOfDay() {
        return Collections.unmodifiableMap(commitsByHourOfDay);
    }
    
    public void incrementCommitsByHour(int hour) {
        commitsByHourOfDay.merge(hour, 1, Integer::sum);
    }
    
    public Map<Integer, Integer> getCommitsByDayOfWeek() {
        return Collections.unmodifiableMap(commitsByDayOfWeek);
    }
    
    public void incrementCommitsByDayOfWeek(int dayOfWeek) {
        commitsByDayOfWeek.merge(dayOfWeek, 1, Integer::sum);
    }
    
    public Map<String, Integer> getCommitsByMonth() {
        return Collections.unmodifiableMap(commitsByMonth);
    }
    
    public void incrementCommitsByMonth(String month) {
        commitsByMonth.merge(month, 1, Integer::sum);
    }
    
    public Map<Integer, Integer> getCommitsByYear() {
        return Collections.unmodifiableMap(commitsByYear);
    }
    
    public void incrementCommitsByYear(int year) {
        commitsByYear.merge(year, 1, Integer::sum);
    }
    
    public Map<String, Integer> getFileTypes() {
        return Collections.unmodifiableMap(fileTypes);
    }
    
    public void incrementFileType(String extension) {
        fileTypes.merge(extension, 1, Integer::sum);
    }
    
    public Map<String, FileStatistics> getFileStats() {
        return Collections.unmodifiableMap(fileStats);
    }
    
    public FileStatistics getOrCreateFileStats(String filePath) {
        return fileStats.computeIfAbsent(filePath, FileStatistics::new);
    }
    
    public Map<String, BranchInfo> getBranches() {
        return Collections.unmodifiableMap(branches);
    }
    
    public void addBranch(String name, BranchInfo info) {
        branches.put(name, info);
    }
    
    public String getMainBranch() {
        return mainBranch;
    }
    
    public void setMainBranch(String mainBranch) {
        this.mainBranch = mainBranch;
    }
    
    public Map<String, CodeMetrics> getFileMetrics() {
        return Collections.unmodifiableMap(fileMetrics);
    }
    
    public void addFileMetrics(String filePath, CodeMetrics metrics) {
        fileMetrics.put(filePath, metrics);
    }
    
    public ProjectHealthMetrics getHealthMetrics() {
        return healthMetrics;
    }
    
    public void setHealthMetrics(ProjectHealthMetrics healthMetrics) {
        this.healthMetrics = healthMetrics;
    }
    
    /**
     * Get age of repository in days
     */
    public long getAgeDays() {
        if (firstCommitDate == null || lastCommitDate == null) {
            return 0;
        }
        return java.time.Duration.between(firstCommitDate, lastCommitDate).toDays();
    }
    
    /**
     * Get total number of authors
     */
    public int getTotalAuthors() {
        return authorStats.size();
    }
}
