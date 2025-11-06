package com.gitstats.model;

/**
 * Statistics for a single file in the repository
 */
public class FileStatistics {
    
    private final String filePath;
    private int revisionCount;
    private long currentSize;
    private long maxSize;
    private int lineCount;
    private String lastModifiedBy;
    
    public FileStatistics(String filePath) {
        this.filePath = filePath;
    }
    
    public String getFilePath() {
        return filePath;
    }
    
    public int getRevisionCount() {
        return revisionCount;
    }
    
    public void incrementRevisionCount() {
        this.revisionCount++;
    }
    
    public long getCurrentSize() {
        return currentSize;
    }
    
    public void setCurrentSize(long currentSize) {
        this.currentSize = currentSize;
        if (currentSize > maxSize) {
            maxSize = currentSize;
        }
    }
    
    public long getMaxSize() {
        return maxSize;
    }
    
    public int getLineCount() {
        return lineCount;
    }
    
    public void setLineCount(int lineCount) {
        this.lineCount = lineCount;
    }
    
    public String getLastModifiedBy() {
        return lastModifiedBy;
    }
    
    public void setLastModifiedBy(String lastModifiedBy) {
        this.lastModifiedBy = lastModifiedBy;
    }
    
    public String getExtension() {
        int lastDot = filePath.lastIndexOf('.');
        if (lastDot > 0 && lastDot < filePath.length() - 1) {
            return filePath.substring(lastDot);
        }
        return "";
    }
}
