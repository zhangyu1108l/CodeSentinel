package cn.codesentinel;

import cn.codesentinel.config.GithubAppProperties;
import cn.codesentinel.config.ReviewContextProperties;
import cn.codesentinel.config.ReviewTaskProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties({
        GithubAppProperties.class,
        ReviewTaskProperties.class,
        ReviewContextProperties.class
})
public class CodeSentinelApplication {

    public static void main(String[] args) {
        SpringApplication.run(CodeSentinelApplication.class, args);
    }
}