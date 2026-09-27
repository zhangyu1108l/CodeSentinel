package cn.codesentinel;

import cn.codesentinel.config.GithubAppProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties(GithubAppProperties.class)
public class CodeSentinelApplication {

    public static void main(String[] args) {
        SpringApplication.run(CodeSentinelApplication.class, args);
    }
}